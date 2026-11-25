from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

from commercepilot.models.enums import ImprovementPriority, ReviewSentiment


class ReviewCreate(BaseModel):
    source_review_id: str = Field(min_length=1, max_length=100)
    source: str = Field(default="novacart", min_length=2, max_length=50)
    rating: int = Field(ge=1, le=5)
    title: str | None = Field(default=None, max_length=255)
    body: str = Field(min_length=10)
    verified_purchase: bool = False
    reviewed_at: datetime

    @field_validator("source_review_id", "source", "body")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("title")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class SimulatedReviewCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rating: int = Field(ge=1, le=5)
    title: Annotated[str, StringConstraints(strip_whitespace=True, max_length=100)] = ""
    body: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=10, max_length=1000)
    ]

    @field_validator("title", "body")
    @classmethod
    def reject_null_characters(cls, value: str) -> str:
        if "\x00" in value:
            raise ValueError("Review text cannot contain null characters.")
        return value


class ReviewRead(ReviewCreate):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    created_at: datetime


class ReviewIngestionResult(BaseModel):
    product_sku: str
    received: int
    created: int
    skipped: int


class ReviewEvidenceSet(BaseModel):
    product_id: UUID
    product_sku: str
    product_name: str
    review_count: int
    average_rating: float
    rating_distribution: dict[int, int]
    verified_purchase_count: int
    reviewed_from: datetime | None
    reviewed_to: datetime | None
    reviews: list[ReviewRead]


class ReviewTheme(BaseModel):
    theme: str = Field(min_length=2, max_length=100)
    summary: str = Field(min_length=10, max_length=500)
    evidence_review_ids: list[UUID] = Field(min_length=1)


class RequestedImprovement(BaseModel):
    recommendation: str = Field(min_length=10, max_length=500)
    rationale: str = Field(min_length=10, max_length=500)
    priority: ImprovementPriority
    evidence_review_ids: list[UUID] = Field(min_length=1)


class ReviewInsight(BaseModel):
    product_sku: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Z0-9-]+$",
    )
    overall_sentiment: ReviewSentiment
    executive_summary: str = Field(min_length=20, max_length=1000)
    strengths: list[ReviewTheme]
    complaints: list[ReviewTheme]
    requested_improvements: list[RequestedImprovement]
    confidence: float = Field(ge=0, le=1)

    @field_validator("product_sku", mode="before")
    @classmethod
    def uppercase_product_sku(cls, value: str) -> str:
        return value.strip().upper()
