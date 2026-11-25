import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi.encoders import jsonable_encoder
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Command, Interrupt
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from commercepilot.core.config import get_settings
from commercepilot.db.models import ApprovalRequest, OrchestrationRun, Product
from commercepilot.db.session import SessionLocal
from commercepilot.graph.checkpoint import build_checkpoint_serializer
from commercepilot.graph.orchestrator_graph import build_orchestrator_graph
from commercepilot.graph.orchestrator_state import CommercePilotState
from commercepilot.models.enums import (
    ApprovalRequestStatus,
    OrchestrationRunStatus,
)
from commercepilot.models.orchestration import HumanApprovalDecision
from commercepilot.models.orchestration_api import RunTimelineEvent

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClaimedOrchestrationRun:
    run_id: UUID
    thread_id: UUID
    product_sku: str
    force_catalog_update: bool
    force_campaign_update: bool
    resume_decision: HumanApprovalDecision | None


def build_initial_state(run: ClaimedOrchestrationRun) -> CommercePilotState:
    return CommercePilotState(
        product_sku=run.product_sku,
        force_catalog_update=run.force_catalog_update,
        force_campaign_update=run.force_campaign_update,
        review_insight=None,
        competitor_insight=None,
        strategy=None,
        catalog_draft=None,
        catalog_draft_id=None,
        catalog_comparison=None,
        catalog_approval_decision=None,
        catalog_publish_action_id=None,
        catalog_execution_result=None,
        campaign_evidence=None,
        campaign_draft=None,
        campaign_draft_id=None,
        campaign_preview=None,
        campaign_approval_decision=None,
        campaign_launch_action_id=None,
        campaign_execution_result=None,
        approval_policy=None,
        approval_decision=None,
        approved_action_ids=[],
        execution_results=[],
        review_error=None,
        competitor_error=None,
        catalog_error=None,
        campaign_error=None,
        error=None,
    )


def list_pending_run_ids(session: Session, *, limit: int = 10) -> list[UUID]:
    return list(
        session.scalars(
            select(OrchestrationRun.id)
            .where(OrchestrationRun.status == OrchestrationRunStatus.PENDING)
            .order_by(OrchestrationRun.created_at)
            .limit(limit)
        )
    )


def claim_orchestration_run(
    session: Session,
    run_id: UUID,
) -> ClaimedOrchestrationRun | None:
    run = session.scalar(
        select(OrchestrationRun)
        .where(
            OrchestrationRun.id == run_id,
            OrchestrationRun.status == OrchestrationRunStatus.PENDING,
        )
        .with_for_update(skip_locked=True)
    )
    if run is None:
        return None

    product = session.get(Product, run.product_id)
    if product is None:
        run.status = OrchestrationRunStatus.FAILED
        run.error = f"Run product not found: {run.product_id}"
        run.completed_at = datetime.now(UTC)
        session.commit()
        return None

    resume_decision: HumanApprovalDecision | None = None
    resume_prefix = "resume_requested:"
    if run.current_stage is not None and run.current_stage.startswith(resume_prefix):
        try:
            approval_id = UUID(run.current_stage.removeprefix(resume_prefix))
        except ValueError as error:
            run.status = OrchestrationRunStatus.FAILED
            run.error = f"Invalid approval resume stage: {run.current_stage}"
            run.completed_at = datetime.now(UTC)
            session.commit()
            raise ValueError(run.error) from error
        approval = session.scalar(
            select(ApprovalRequest).where(
                ApprovalRequest.id == approval_id,
                ApprovalRequest.run_id == run.id,
            )
        )
        if (
            approval is None
            or approval.status is ApprovalRequestStatus.PENDING
            or approval.reviewer is None
        ):
            run.status = OrchestrationRunStatus.FAILED
            run.error = f"Approval decision unavailable for resume: {approval_id}"
            run.completed_at = datetime.now(UTC)
            session.commit()
            raise ValueError(run.error)
        resume_decision = HumanApprovalDecision(
            approved=approval.status is ApprovalRequestStatus.APPROVED,
            reviewer=approval.reviewer,
            comment=approval.comment,
        )

    run.status = OrchestrationRunStatus.RUNNING
    run.current_stage = "resuming" if resume_decision is not None else "starting"
    if run.started_at is None:
        run.started_at = datetime.now(UTC)
    run.error = None
    session.commit()
    return ClaimedOrchestrationRun(
        run_id=run.id,
        thread_id=run.thread_id,
        product_sku=product.sku,
        force_catalog_update=run.force_catalog_update,
        force_campaign_update=run.force_campaign_update,
        resume_decision=resume_decision,
    )


def record_approval_interrupt(
    session: Session,
    run_id: UUID,
    interrupt: Interrupt,
    partial_result: dict[str, Any],
) -> None:
    run = session.get(OrchestrationRun, run_id)
    if run is None:
        raise ValueError(f"Orchestration run not found: {run_id}")
    if not isinstance(interrupt.value, dict):
        raise ValueError("Approval interrupt payload must be an object.")

    payload = jsonable_encoder(interrupt.value)
    approval_type = str(payload.get("type", "human_approval_required"))
    existing = session.scalar(
        select(ApprovalRequest).where(
            ApprovalRequest.run_id == run_id,
            ApprovalRequest.interrupt_id == interrupt.id,
        )
    )
    if existing is None:
        session.add(
            ApprovalRequest(
                run_id=run_id,
                interrupt_id=interrupt.id,
                approval_type=approval_type,
                payload=payload,
                status=ApprovalRequestStatus.PENDING,
            )
        )
    elif existing.payload != payload or existing.approval_type != approval_type:
        raise ValueError(
            f"Approval interrupt changed after persistence: {interrupt.id}"
        )

    run.status = OrchestrationRunStatus.AWAITING_APPROVAL
    run.current_stage = approval_type
    run.result = serialize_graph_result(partial_result)
    session.commit()


def record_run_completion(
    session: Session,
    run_id: UUID,
    result: dict[str, Any],
) -> None:
    run = session.get(OrchestrationRun, run_id)
    if run is None:
        raise ValueError(f"Orchestration run not found: {run_id}")
    run.result = serialize_graph_result(result)
    run.status = OrchestrationRunStatus.COMPLETED
    run.current_stage = "completed"
    run.completed_at = datetime.now(UTC)
    run.error = None
    session.commit()


def record_run_failure(
    session: Session,
    run_id: UUID,
    error: Exception | str,
) -> None:
    run = session.get(OrchestrationRun, run_id)
    if run is None:
        return
    run.status = OrchestrationRunStatus.FAILED
    run.current_stage = "failed"
    run.error = str(error)
    run.completed_at = datetime.now(UTC)
    session.commit()


def serialize_graph_result(result: dict[str, Any]) -> dict[str, Any]:
    return jsonable_encoder(
        {key: value for key, value in result.items() if key != "__interrupt__"}
    )


async def execute_orchestration_run(run_id: UUID) -> bool:
    with SessionLocal() as session:
        claimed_run = claim_orchestration_run(session, run_id)
    if claimed_run is None:
        return False

    def record_stage_event(event: RunTimelineEvent) -> None:
        try:
            with SessionLocal() as session:
                # Review and competitor stages can complete concurrently.
                run = session.get(OrchestrationRun, run_id, with_for_update=True)
                if run is not None:
                    run.stage_events = [
                        *(run.stage_events or []),
                        event.model_dump(mode="json"),
                    ]
                    session.commit()
        except SQLAlchemyError:
            logger.warning("Could not persist stage event for run %s", run_id)

    settings = get_settings()
    config = {
        "configurable": {
            "thread_id": str(claimed_run.thread_id),
        }
    }
    try:
        async with AsyncPostgresSaver.from_conn_string(
            settings.checkpoint_database_url,
            serde=build_checkpoint_serializer(),
        ) as checkpointer:
            await checkpointer.setup()
            graph = build_orchestrator_graph(
                checkpointer=checkpointer,
                stage_observer=record_stage_event,
            )
            graph_input: CommercePilotState | Command = (
                Command(resume=claimed_run.resume_decision.model_dump(mode="json"))
                if claimed_run.resume_decision is not None
                else build_initial_state(claimed_run)
            )
            result = await graph.ainvoke(graph_input, config=config)

        error = result.get("error")
        if error is not None:
            raise RuntimeError(str(error))

        interrupts: tuple[Interrupt, ...] = result.get("__interrupt__", ())
        with SessionLocal() as session:
            if interrupts:
                record_approval_interrupt(
                    session,
                    run_id,
                    interrupts[0],
                    result,
                )
            else:
                record_run_completion(session, run_id, result)
        return True
    except Exception as error:
        with SessionLocal() as session:
            record_run_failure(session, run_id, error)
        return False
