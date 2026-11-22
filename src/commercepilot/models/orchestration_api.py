from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from commercepilot.models.enums import (
    ApprovalRequestStatus,
    OrchestrationRunStatus,
)


class OrchestrationRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_sku: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Z0-9-]+$",
    )
    force_catalog_update: bool = False
    force_campaign_update: bool = False


class OrchestrationRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    thread_id: UUID
    product_id: UUID
    product_sku: str
    product_name: str
    status: OrchestrationRunStatus
    current_stage: str | None
    force_catalog_update: bool
    force_campaign_update: bool
    result: dict[str, Any] | None
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApprovalRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    interrupt_id: str
    approval_type: str
    payload: dict[str, Any]
    status: ApprovalRequestStatus
    reviewer: str | None
    comment: str | None
    decided_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    reviewer: str = Field(min_length=1, max_length=100)
    comment: str | None = Field(default=None, max_length=2000)


class RunTimelineEvent(BaseModel):
    id: str
    event_type: str
    title: str
    status: Literal["completed", "pending", "approved", "rejected", "failed"]
    occurred_at: datetime | None
    approval_id: UUID | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class RunTimelineRead(BaseModel):
    run_id: UUID
    product_sku: str
    product_name: str
    status: OrchestrationRunStatus
    current_stage: str | None
    events: list[RunTimelineEvent]


class ApprovalInboxItem(ApprovalRequestRead):
    product_id: UUID
    product_sku: str
    product_name: str
    run_status: OrchestrationRunStatus
    run_current_stage: str | None
