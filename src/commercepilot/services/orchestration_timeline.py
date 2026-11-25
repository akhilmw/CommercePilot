from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload, selectinload

from commercepilot.db.models import ApprovalRequest, OrchestrationRun
from commercepilot.models.enums import (
    ApprovalRequestStatus,
    OrchestrationRunStatus,
)
from commercepilot.models.orchestration_api import (
    ApprovalInboxItem,
    RunTimelineEvent,
    RunTimelineRead,
)
from commercepilot.services.orchestration_runs import (
    OrchestrationRunNotFoundError,
)

APPROVAL_TITLES = {
    "catalog_publish_approval_required": "Catalog update approval",
    "campaign_launch_approval_required": "Campaign launch approval",
    "human_approval_required": "Human approval",
}


def _approval_title(approval_type: str) -> str:
    return APPROVAL_TITLES.get(
        approval_type,
        approval_type.replace("_", " ").title(),
    )


def build_run_timeline(run: OrchestrationRun) -> RunTimelineRead:
    events = [
        RunTimelineEvent(
            id=f"run:{run.id}:created",
            event_type="run_created",
            title="Intelligence cycle created",
            status="completed",
            occurred_at=run.created_at,
        )
    ]
    if run.started_at is not None:
        events.append(
            RunTimelineEvent(
                id=f"run:{run.id}:started",
                event_type="run_started",
                title="Agent workflow started",
                status="completed",
                occurred_at=run.started_at,
            )
        )

    for approval in sorted(run.approval_requests, key=lambda item: item.created_at):
        title = _approval_title(approval.approval_type)
        events.append(
            RunTimelineEvent(
                id=f"approval:{approval.id}:requested",
                event_type="approval_requested",
                title=f"{title} requested",
                status=(
                    "pending"
                    if approval.status is ApprovalRequestStatus.PENDING
                    else "completed"
                ),
                occurred_at=approval.created_at,
                approval_id=approval.id,
                details={"approval_type": approval.approval_type},
            )
        )
        if approval.decided_at is not None:
            events.append(
                RunTimelineEvent(
                    id=f"approval:{approval.id}:decided",
                    event_type="approval_decided",
                    title=f"{title} {approval.status.value}",
                    status=approval.status.value,
                    occurred_at=approval.decided_at,
                    approval_id=approval.id,
                    details={
                        "approval_type": approval.approval_type,
                        "reviewer": approval.reviewer,
                        "comment": approval.comment,
                    },
                )
            )

    if run.completed_at is not None:
        failed = run.status is OrchestrationRunStatus.FAILED
        events.append(
            RunTimelineEvent(
                id=f"run:{run.id}:finished",
                event_type="run_failed" if failed else "run_completed",
                title=(
                    "Intelligence cycle failed"
                    if failed
                    else "Intelligence cycle completed"
                ),
                status="failed" if failed else "completed",
                occurred_at=run.completed_at,
                details={"error": run.error} if failed else {},
            )
        )

    events.extend(
        RunTimelineEvent.model_validate(event) for event in (run.stage_events or [])
    )
    events.sort(key=lambda event: event.occurred_at or run.created_at)
    return RunTimelineRead(
        run_id=run.id,
        product_sku=run.product.sku,
        product_name=run.product.name,
        status=run.status,
        current_stage=run.current_stage,
        events=events,
    )


def get_run_timeline(session: Session, run_id: UUID) -> RunTimelineRead:
    run = session.scalar(
        select(OrchestrationRun)
        .options(
            joinedload(OrchestrationRun.product),
            selectinload(OrchestrationRun.approval_requests),
        )
        .where(OrchestrationRun.id == run_id)
    )
    if run is None:
        raise OrchestrationRunNotFoundError(f"Orchestration run not found: {run_id}")
    return build_run_timeline(run)


def list_approval_inbox(
    session: Session,
    *,
    approval_status: ApprovalRequestStatus = ApprovalRequestStatus.PENDING,
    limit: int = 50,
) -> list[ApprovalInboxItem]:
    approvals = list(
        session.scalars(
            select(ApprovalRequest)
            .options(
                joinedload(ApprovalRequest.run).joinedload(OrchestrationRun.product)
            )
            .where(ApprovalRequest.status == approval_status)
            .order_by(ApprovalRequest.created_at.desc())
            .limit(limit)
        )
    )
    return [
        ApprovalInboxItem(
            **approval.__dict__,
            product_id=approval.run.product.id,
            product_sku=approval.run.product.sku,
            product_name=approval.run.product.name,
            run_status=approval.run.status,
            run_current_stage=approval.run.current_stage,
        )
        for approval in approvals
    ]
