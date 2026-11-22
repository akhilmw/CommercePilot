from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from langgraph.types import Interrupt
from sqlalchemy.orm import Session

from commercepilot.db.models import ApprovalRequest, OrchestrationRun, Product
from commercepilot.models.enums import (
    ApprovalRequestStatus,
    OrchestrationRunStatus,
)
from commercepilot.services.orchestration_execution import (
    ClaimedOrchestrationRun,
    build_initial_state,
    claim_orchestration_run,
    record_approval_interrupt,
    record_run_completion,
)


def make_run() -> tuple[OrchestrationRun, Product]:
    product = Product(
        id=uuid4(),
        sku="NOVA-AUDIO-001",
        name="NovaSound Pro",
        category="wireless-headphones",
        description="Wireless over-ear headphones.",
        price=99.99,
        currency="USD",
    )
    run = OrchestrationRun(
        id=uuid4(),
        thread_id=uuid4(),
        product_id=product.id,
        status=OrchestrationRunStatus.PENDING,
        force_catalog_update=False,
        force_campaign_update=True,
    )
    return run, product


def test_claim_pending_run_marks_it_running() -> None:
    session = MagicMock(spec=Session)
    run, product = make_run()
    session.scalar.return_value = run
    session.get.return_value = product

    claimed = claim_orchestration_run(session, run.id)

    assert claimed == ClaimedOrchestrationRun(
        run_id=run.id,
        thread_id=run.thread_id,
        product_sku=product.sku,
        force_catalog_update=False,
        force_campaign_update=True,
        resume_decision=None,
    )
    assert run.status is OrchestrationRunStatus.RUNNING
    assert run.current_stage == "starting"
    assert run.started_at is not None
    session.commit.assert_called_once()


def test_initial_state_is_isolated_to_claimed_product() -> None:
    run, product = make_run()
    claimed = ClaimedOrchestrationRun(
        run_id=run.id,
        thread_id=run.thread_id,
        product_sku=product.sku,
        force_catalog_update=False,
        force_campaign_update=True,
        resume_decision=None,
    )

    state = build_initial_state(claimed)

    assert state["product_sku"] == product.sku
    assert state["force_campaign_update"] is True
    assert state["strategy"] is None
    assert state["approved_action_ids"] == []


def test_claim_decided_approval_builds_resume_command_input() -> None:
    session = MagicMock(spec=Session)
    run, product = make_run()
    approval = ApprovalRequest(
        id=uuid4(),
        run_id=run.id,
        interrupt_id="interrupt-1",
        approval_type="catalog_publish_approval_required",
        payload={},
        status=ApprovalRequestStatus.REJECTED,
        reviewer="local-user",
        comment="Needs revision.",
    )
    run.current_stage = f"resume_requested:{approval.id}"
    original_started_at = datetime.now(UTC)
    run.started_at = original_started_at
    session.scalar.side_effect = [run, approval]
    session.get.return_value = product

    claimed = claim_orchestration_run(session, run.id)

    assert claimed is not None
    assert claimed.resume_decision is not None
    assert claimed.resume_decision.approved is False
    assert claimed.resume_decision.reviewer == "local-user"
    assert run.status is OrchestrationRunStatus.RUNNING
    assert run.current_stage == "resuming"
    assert run.started_at is original_started_at


def test_record_interrupt_creates_pending_approval() -> None:
    session = MagicMock(spec=Session)
    run, _ = make_run()
    run.status = OrchestrationRunStatus.RUNNING
    session.get.return_value = run
    session.scalar.return_value = None
    interrupt = Interrupt(
        id="approval-interrupt-1",
        value={
            "type": "campaign_launch_approval_required",
            "product_sku": "NOVA-AUDIO-001",
        },
    )

    record_approval_interrupt(
        session,
        run.id,
        interrupt,
        {"product_sku": "NOVA-AUDIO-001", "__interrupt__": (interrupt,)},
    )

    approval = session.add.call_args.args[0]
    assert isinstance(approval, ApprovalRequest)
    assert approval.interrupt_id == interrupt.id
    assert approval.status is ApprovalRequestStatus.PENDING
    assert run.status is OrchestrationRunStatus.AWAITING_APPROVAL
    assert run.current_stage == "campaign_launch_approval_required"
    assert run.result == {"product_sku": "NOVA-AUDIO-001"}
    session.commit.assert_called_once()


def test_record_completion_stores_json_safe_result() -> None:
    session = MagicMock(spec=Session)
    run, _ = make_run()
    run.status = OrchestrationRunStatus.RUNNING
    session.get.return_value = run
    action_id = uuid4()

    record_run_completion(
        session,
        run.id,
        {"approved_action_ids": [action_id], "error": None},
    )

    assert run.status is OrchestrationRunStatus.COMPLETED
    assert run.current_stage == "completed"
    assert run.result == {
        "approved_action_ids": [str(action_id)],
        "error": None,
    }
    assert run.completed_at is not None
    session.commit.assert_called_once()
