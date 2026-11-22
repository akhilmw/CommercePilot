from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from commercepilot.db.models import ApprovalRequest, OrchestrationRun
from commercepilot.models.enums import (
    ApprovalRequestStatus,
    OrchestrationRunStatus,
)
from commercepilot.models.orchestration_api import ApprovalDecisionRequest


class ApprovalRequestNotFoundError(ValueError):
    pass


class ApprovalRequestAlreadyDecidedError(ValueError):
    pass


class RunNotAwaitingApprovalError(ValueError):
    pass


def list_approval_requests(
    session: Session,
    run_id: UUID,
) -> list[ApprovalRequest]:
    run = session.get(OrchestrationRun, run_id)
    if run is None:
        raise ApprovalRequestNotFoundError(f"Orchestration run not found: {run_id}")
    return list(
        session.scalars(
            select(ApprovalRequest)
            .where(ApprovalRequest.run_id == run_id)
            .order_by(ApprovalRequest.created_at)
        )
    )


def submit_approval_decision(
    session: Session,
    run_id: UUID,
    approval_id: UUID,
    decision: ApprovalDecisionRequest,
) -> ApprovalRequest:
    run = session.scalar(
        select(OrchestrationRun).where(OrchestrationRun.id == run_id).with_for_update()
    )
    if run is None:
        raise ApprovalRequestNotFoundError(f"Orchestration run not found: {run_id}")

    approval = session.scalar(
        select(ApprovalRequest)
        .where(
            ApprovalRequest.id == approval_id,
            ApprovalRequest.run_id == run_id,
        )
        .with_for_update()
    )
    if approval is None:
        raise ApprovalRequestNotFoundError(f"Approval request not found: {approval_id}")
    if approval.status is not ApprovalRequestStatus.PENDING:
        raise ApprovalRequestAlreadyDecidedError(
            f"Approval request already decided: {approval_id}"
        )
    if run.status is not OrchestrationRunStatus.AWAITING_APPROVAL:
        raise RunNotAwaitingApprovalError(f"Run is not awaiting approval: {run.status}")

    approval.status = (
        ApprovalRequestStatus.APPROVED
        if decision.approved
        else ApprovalRequestStatus.REJECTED
    )
    approval.reviewer = decision.reviewer
    approval.comment = decision.comment
    approval.decided_at = datetime.now(UTC)
    run.status = OrchestrationRunStatus.PENDING
    run.current_stage = f"resume_requested:{approval.id}"
    run.error = None
    session.commit()
    session.refresh(approval)
    return approval
