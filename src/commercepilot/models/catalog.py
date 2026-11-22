from typing import Any
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_serializer,
    model_validator,
)

from commercepilot.models.competitor import CompetitorInsight
from commercepilot.models.enums import CatalogDraftStatus
from commercepilot.models.product import ProductRead
from commercepilot.models.review import ReviewInsight


class CatalogBullet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=10, max_length=250)
    evidence_ids: list[UUID] = Field(min_length=1)


class CatalogEvidenceSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: ProductRead
    review_insight: ReviewInsight
    competitor_insight: CompetitorInsight

    @model_validator(mode="after")
    def validate_consistent_product_evidence(self) -> "CatalogEvidenceSet":
        if self.review_insight.product_sku != self.product.sku:
            raise ValueError("Review insight SKU does not match the product.")
        if self.competitor_insight.product_sku != self.product.sku:
            raise ValueError("Competitor insight SKU does not match the product.")
        if self.competitor_insight.our_price != self.product.price:
            raise ValueError(
                "Competitor insight price does not match the current product price."
            )
        if self.competitor_insight.currency != self.product.currency:
            raise ValueError("Competitor insight currency does not match the product.")
        return self


class CatalogDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_sku: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Z0-9-]+$",
    )
    seo_title: str = Field(min_length=10, max_length=70)
    meta_description: str = Field(min_length=50, max_length=160)
    product_description: str = Field(min_length=100, max_length=1500)
    feature_bullets: list[CatalogBullet] = Field(
        min_length=3,
        max_length=6,
    )
    seo_keywords: list[str] = Field(min_length=3, max_length=10)
    target_audience: str = Field(min_length=10, max_length=300)
    supporting_evidence_ids: list[UUID] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)


class CatalogClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=1500)
    evidence_ids: list[UUID] = Field(min_length=1)


class CatalogClaimVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1, max_length=64)
    supported: bool
    rationale: str = Field(min_length=5, max_length=500)


class CatalogSemanticVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[CatalogClaimVerification] = Field(min_length=1)


CatalogFieldValue = str | list[str] | list[dict[str, Any]] | None


class CatalogFieldDiff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    label: str
    current_value: CatalogFieldValue
    proposed_value: CatalogFieldValue
    changed: bool


class CatalogComparison(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: UUID
    product_id: UUID
    product_sku: str
    status: CatalogDraftStatus
    current_catalog_version: int = Field(ge=1)
    expected_catalog_version: int = Field(ge=1)
    is_stale: bool
    fields: list[CatalogFieldDiff] = Field(min_length=1)

    @field_serializer("fields")
    def serialize_fields(self, fields: list[Any]) -> list[dict[str, Any]]:
        """Normalize nested diffs restored from durable graph checkpoints."""
        return [
            CatalogFieldDiff.model_validate(field).model_dump(mode="json")
            for field in fields
        ]

    @computed_field
    @property
    def has_changes(self) -> bool:
        return any(
            field.changed
            if isinstance(field, CatalogFieldDiff)
            else bool(field["changed"])
            for field in self.fields
        )
