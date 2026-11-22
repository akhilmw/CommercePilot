from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from commercepilot.db.session import get_db
from commercepilot.models.enums import ApprovalRequestStatus
from commercepilot.models.orchestration_api import ApprovalInboxItem
from commercepilot.services.orchestration_timeline import list_approval_inbox

router = APIRouter(prefix="/api/approvals", tags=["approvals"])


@router.get("", response_model=list[ApprovalInboxItem])
def read_approval_inbox(
    session: Annotated[Session, Depends(get_db)],
    approval_status: Annotated[
        ApprovalRequestStatus,
        Query(alias="status"),
    ] = ApprovalRequestStatus.PENDING,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ApprovalInboxItem]:
    return list_approval_inbox(
        session,
        approval_status=approval_status,
        limit=limit,
    )
