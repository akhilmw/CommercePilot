from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from commercepilot.db.models import ApprovalRequest, OrchestrationRun
from commercepilot.models.enums import (
    ApprovalRequestStatus,
    OrchestrationRunStatus,
)
from commercepilot.models.orchestration_api import ApprovalDecisionRequest
from commercepilot.services.orchestration_approvals import (
    ApprovalRequestAlreadyDecidedError,
    RunNotAwaitingApprovalError,
    submit_approval_decision,
)


def make_pending_approval() -> tuple[OrchestrationRun, ApprovalRequest]:
    run = OrchestrationRun(
        id=uuid4(),
        product_id=uuid4(),
        status=OrchestrationRunStatus.AWAITING_APPROVAL,
        current_stage="catalog_publish_approval_required",
    )
    approval = ApprovalRequest(
        id=uuid4(),
        run_id=run.id,
        interrupt_id="interrupt-1",
        approval_type="catalog_publish_approval_required",
        payload={"product_sku": "NOVA-AUDIO-001"},
        status=ApprovalRequestStatus.PENDING,
    )
    return run, approval


@pytest.mark.parametrize(
    ("approved", "expected_status"),
    [
        (True, ApprovalRequestStatus.APPROVED),
        (False, ApprovalRequestStatus.REJECTED),
    ],
)
def test_submit_decision_queues_checkpoint_resume(
    approved: bool,
    expected_status: ApprovalRequestStatus,
) -> None:
    session = MagicMock(spec=Session)
    run, approval = make_pending_approval()
    session.scalar.side_effect = [run, approval]
    decision = ApprovalDecisionRequest(
        approved=approved,
        reviewer="local-user",
        comment="Reviewed against evidence.",
    )

    result = submit_approval_decision(
        session,
        run.id,
        approval.id,
        decision,
    )

    assert result is approval
    assert approval.status is expected_status
    assert approval.reviewer == "local-user"
    assert approval.decided_at is not None
    assert run.status is OrchestrationRunStatus.PENDING
    assert run.current_stage == f"resume_requested:{approval.id}"
    session.commit.assert_called_once()
    session.refresh.assert_called_once_with(approval)


def test_submit_decision_rejects_repeated_decision() -> None:
    session = MagicMock(spec=Session)
    run, approval = make_pending_approval()
    approval.status = ApprovalRequestStatus.APPROVED
    session.scalar.side_effect = [run, approval]

    with pytest.raises(ApprovalRequestAlreadyDecidedError):
        submit_approval_decision(
            session,
            run.id,
            approval.id,
            ApprovalDecisionRequest(approved=True, reviewer="local-user"),
        )

    session.commit.assert_not_called()


def test_submit_decision_requires_paused_run() -> None:
    session = MagicMock(spec=Session)
    run, approval = make_pending_approval()
    run.status = OrchestrationRunStatus.RUNNING
    session.scalar.side_effect = [run, approval]

    with pytest.raises(RunNotAwaitingApprovalError):
        submit_approval_decision(
            session,
            run.id,
            approval.id,
            ApprovalDecisionRequest(approved=False, reviewer="local-user"),
        )

    session.commit.assert_not_called()
