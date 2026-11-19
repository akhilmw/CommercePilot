from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from commercepilot.models.enums import (
    CompetitiveThreatLevel,
    ImprovementPriority,
    PriceChangeType,
)


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
    current_snapshot_id: UUID
    previous_snapshot_id: UUID | None
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


class CompetitorEvidenceSet(BaseModel):
    product_id: UUID
    product_sku: str
    product_name: str
    our_price: Decimal
    currency: str
    price_changes: list[CompetitorPriceChange]


class CompetitorFinding(BaseModel):
    competitor_product_id: UUID
    competitor_name: str = Field(min_length=2, max_length=255)
    threat_level: CompetitiveThreatLevel
    summary: str = Field(min_length=10, max_length=750)
    evidence_snapshot_ids: list[UUID] = Field(min_length=1)


class CompetitiveRecommendation(BaseModel):
    recommendation: str = Field(min_length=10, max_length=500)
    rationale: str = Field(min_length=10, max_length=750)
    priority: ImprovementPriority
    evidence_snapshot_ids: list[UUID] = Field(min_length=1)


class CompetitorInsight(BaseModel):
    product_sku: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Z0-9-]+$",
    )
    overall_threat_level: CompetitiveThreatLevel
    market_summary: str = Field(min_length=20, max_length=1000)
    findings: list[CompetitorFinding] = Field(min_length=1)
    recommended_actions: list[CompetitiveRecommendation]
    confidence: float = Field(ge=0, le=1)

    @field_validator("product_sku", mode="before")
    @classmethod
    def uppercase_product_sku(cls, value: str) -> str:
        return value.strip().upper()
