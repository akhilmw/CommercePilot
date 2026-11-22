from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from commercepilot.db.session import get_db
from commercepilot.models.orchestration_api import (
    ApprovalDecisionRequest,
    ApprovalRequestRead,
    OrchestrationRunCreate,
    OrchestrationRunRead,
    RunTimelineRead,
)
from commercepilot.services.orchestration_approvals import (
    ApprovalRequestAlreadyDecidedError,
    ApprovalRequestNotFoundError,
    RunNotAwaitingApprovalError,
    list_approval_requests,
    submit_approval_decision,
)
from commercepilot.services.orchestration_runs import (
    ActiveOrchestrationRunError,
    OrchestrationRunNotFoundError,
    ProductNotFoundError,
    create_orchestration_run,
    get_orchestration_run,
)
from commercepilot.services.orchestration_timeline import get_run_timeline

router = APIRouter(prefix="/api/runs", tags=["orchestration"])


@router.post(
    "",
    response_model=OrchestrationRunRead,
    status_code=status.HTTP_201_CREATED,
)
def create_run(
    request: OrchestrationRunCreate,
    session: Annotated[Session, Depends(get_db)],
) -> OrchestrationRunRead:
    try:
        run = create_orchestration_run(session, request)
    except ProductNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except ActiveOrchestrationRunError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": str(error),
                "active_run_id": str(error.run_id),
            },
        ) from error
    return OrchestrationRunRead.model_validate(run)


@router.get("/{run_id}", response_model=OrchestrationRunRead)
def read_run(
    run_id: UUID,
    session: Annotated[Session, Depends(get_db)],
) -> OrchestrationRunRead:
    try:
        run = get_orchestration_run(session, run_id)
    except OrchestrationRunNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    return OrchestrationRunRead.model_validate(run)


@router.get("/{run_id}/timeline", response_model=RunTimelineRead)
def read_run_timeline(
    run_id: UUID,
    session: Annotated[Session, Depends(get_db)],
) -> RunTimelineRead:
    try:
        return get_run_timeline(session, run_id)
    except OrchestrationRunNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.get(
    "/{run_id}/approvals",
    response_model=list[ApprovalRequestRead],
)
def read_approvals(
    run_id: UUID,
    session: Annotated[Session, Depends(get_db)],
) -> list[ApprovalRequestRead]:
    try:
        approvals = list_approval_requests(session, run_id)
    except ApprovalRequestNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    return [ApprovalRequestRead.model_validate(value) for value in approvals]


@router.post(
    "/{run_id}/approvals/{approval_id}",
    response_model=ApprovalRequestRead,
)
def decide_approval(
    run_id: UUID,
    approval_id: UUID,
    decision: ApprovalDecisionRequest,
    session: Annotated[Session, Depends(get_db)],
) -> ApprovalRequestRead:
    try:
        approval = submit_approval_decision(
            session,
            run_id,
            approval_id,
            decision,
        )
    except ApprovalRequestNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except (
        ApprovalRequestAlreadyDecidedError,
        RunNotAwaitingApprovalError,
    ) as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
    return ApprovalRequestRead.model_validate(approval)
