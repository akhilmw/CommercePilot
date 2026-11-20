from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from commercepilot.models.competitor import CompetitorInsight
from commercepilot.models.enums import (
    CampaignChannel,
    CampaignDraftStatus,
    ProductStatus,
)
from commercepilot.models.orchestration import CommerceStrategy
from commercepilot.models.product import ProductRead
from commercepilot.models.review import ReviewInsight


class CampaignEvidenceSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product: ProductRead
    review_insight: ReviewInsight
    competitor_insight: CompetitorInsight
    strategy: CommerceStrategy

    @model_validator(mode="after")
    def validate_consistent_campaign_evidence(self) -> "CampaignEvidenceSet":
        product = self.product
        if product.status is not ProductStatus.ACTIVE:
            raise ValueError("Campaign product must be active.")
        if self.review_insight.product_sku != product.sku:
            raise ValueError("Review insight SKU does not match the product.")
        if self.competitor_insight.product_sku != product.sku:
            raise ValueError("Competitor insight SKU does not match the product.")
        if self.strategy.product_sku != product.sku:
            raise ValueError("Strategy SKU does not match the product.")
        if self.competitor_insight.our_price != product.price:
            raise ValueError(
                "Competitor insight price does not match the current product price."
            )
        if self.competitor_insight.currency != product.currency:
            raise ValueError("Competitor insight currency does not match the product.")
        if (
            product.seo_title is None
            or product.meta_description is None
            or not product.feature_bullets
            or not product.seo_keywords
            or product.target_audience is None
        ):
            raise ValueError(
                "Campaign generation requires a published product catalog."
            )
        return self


class CampaignAsset(BaseModel):
    model_config = ConfigDict(extra="forbid")

    channel: CampaignChannel
    headline: str = Field(min_length=10, max_length=120)
    body: str = Field(min_length=30, max_length=1000)
    call_to_action: str = Field(min_length=2, max_length=80)
    evidence_ids: list[UUID] = Field(min_length=1)


class CampaignDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_sku: str = Field(
        min_length=3,
        max_length=64,
        pattern=r"^[A-Z0-9-]+$",
    )
    name: str = Field(min_length=5, max_length=120)
    objective: str = Field(min_length=20, max_length=500)
    target_audience: str = Field(min_length=10, max_length=500)
    core_message: str = Field(min_length=20, max_length=1000)
    assets: list[CampaignAsset] = Field(min_length=3, max_length=3)
    duration_days: int = Field(ge=1, le=90)
    success_metrics: list[str] = Field(min_length=1, max_length=6)
    supporting_evidence_ids: list[UUID] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)

    @model_validator(mode="after")
    def validate_campaign_evidence(self) -> "CampaignDraft":
        channels = [asset.channel for asset in self.assets]
        if len(channels) != len(set(channels)):
            raise ValueError("Campaign assets must use unique channels.")

        supporting_ids = set(self.supporting_evidence_ids)
        for asset in self.assets:
            if not set(asset.evidence_ids).issubset(supporting_ids):
                raise ValueError(
                    "Campaign asset evidence must be included in supporting "
                    "evidence IDs."
                )
        return self


class CampaignClaim(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[UUID] = Field(min_length=1)


class CampaignClaimVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    claim_id: str = Field(min_length=1, max_length=64)
    supported: bool
    rationale: str = Field(min_length=5, max_length=500)


class CampaignSemanticVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    results: list[CampaignClaimVerification] = Field(min_length=1)


class CampaignLaunchPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: UUID
    product_id: UUID
    product_sku: str
    status: CampaignDraftStatus
    source_catalog_version: int = Field(ge=1)
    current_catalog_version: int = Field(ge=1)
    source_price: Decimal = Field(ge=0)
    current_price: Decimal = Field(ge=0)
    is_stale: bool
    name: str
    objective: str
    target_audience: str
    core_message: str
    assets: list[CampaignAsset]
    duration_days: int
    success_metrics: list[str]
    confidence: Decimal = Field(ge=0, le=1)
