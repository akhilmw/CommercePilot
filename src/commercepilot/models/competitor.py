from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from commercepilot.models.enums import PriceChangeType


class CompetitorCreate(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str = Field(
        min_length=2,
        max_length=100,
        pattern=r"^[a-z0-9-]+$",
    )
    active: bool = True

    @field_validator("name", "slug")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class CompetitorRead(CompetitorCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


class CompetitorProductCreate(BaseModel):
    competitor_id: UUID
    product_id: UUID
    competitor_sku: str = Field(
        min_length=3,
        max_length=100,
        pattern=r"^[A-Z0-9-]+$",
    )
    name: str = Field(min_length=2, max_length=255)
    description: str | None = None
    specifications: dict[str, Any] = Field(default_factory=dict)

    @field_validator("competitor_sku", mode="before")
    @classmethod
    def uppercase_sku(cls, value: str) -> str:
        return value.strip().upper()


class CompetitorProductRead(CompetitorProductCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime
    updated_at: datetime


class CompetitorPriceSnapshotCreate(BaseModel):
    competitor_product_id: UUID
    price: Decimal = Field(
        ge=0,
        max_digits=10,
        decimal_places=2,
    )
    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
        pattern=r"^[A-Z]{3}$",
    )
    promotion: str | None = Field(default=None, max_length=255)
    observed_at: datetime

    @field_validator("currency", mode="before")
    @classmethod
    def uppercase_currency(cls, value: str) -> str:
        return value.strip().upper()


class CompetitorPriceSnapshotRead(CompetitorPriceSnapshotCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    created_at: datetime


class CompetitorPriceChange(BaseModel):
    competitor_product_id: UUID
    competitor_name: str
    competitor_product_name: str
    previous_price: Decimal | None
    current_price: Decimal
    change_type: PriceChangeType
    change_amount: Decimal
    change_percent: Decimal
    our_price: Decimal
    price_difference_from_ours: Decimal
    is_cheaper_than_ours: bool
    promotion: str | None
    observed_at: datetime
