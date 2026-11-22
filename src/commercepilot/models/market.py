from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from commercepilot.models.enums import PriceChangeType


class MarketSnapshotCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    competitor_sku: str = Field(
        min_length=3,
        max_length=100,
        pattern=r"^[A-Z0-9-]+$",
    )
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    promotion: str | None = Field(default=None, max_length=255)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("competitor_sku", mode="before")
    @classmethod
    def uppercase_competitor_sku(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("observed_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("observed_at must include a timezone")
        return value


class MarketCompetitorView(BaseModel):
    competitor_product_id: UUID
    competitor_sku: str
    competitor_name: str
    competitor_product_name: str
    current_snapshot_id: UUID
    previous_snapshot_id: UUID | None
    previous_price: Decimal | None
    current_price: Decimal
    currency: str
    change_type: PriceChangeType
    change_amount: Decimal
    change_percent: Decimal
    promotion: str | None
    observed_at: datetime
    price_difference_from_ours: Decimal
    is_cheaper_than_ours: bool


class MarketOverview(BaseModel):
    product_id: UUID
    product_sku: str
    product_name: str
    our_price: Decimal
    currency: str
    competitors: list[MarketCompetitorView]


class MarketSnapshotResult(MarketCompetitorView):
    product_sku: str
