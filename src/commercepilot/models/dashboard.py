from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from commercepilot.models.enums import OrchestrationRunStatus, ProductStatus


class LatestRunSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: OrchestrationRunStatus
    current_stage: str | None
    created_at: datetime
    completed_at: datetime | None


class ProductPortfolioItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sku: str
    name: str
    category: str
    price: Decimal
    currency: str
    status: ProductStatus
    catalog_version: int = Field(ge=1)
    review_count: int = Field(ge=0)
    competitor_count: int = Field(ge=0)
    pending_approval_count: int = Field(ge=0)
    latest_run: LatestRunSummary | None
    updated_at: datetime
