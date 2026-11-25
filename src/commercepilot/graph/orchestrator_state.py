from typing import NotRequired, TypedDict
from uuid import UUID

from commercepilot.mcp.client import (
    LaunchCampaignResult,
    PublishCatalogUpdateResult,
    UpdateProductPriceResult,
)
from commercepilot.models.campaign import (
    CampaignDraft,
    CampaignEvidenceSet,
    CampaignLaunchPreview,
)
from commercepilot.models.catalog import CatalogComparison, CatalogDraft
from commercepilot.models.competitor import CompetitorInsight
from commercepilot.models.orchestration import (
    ApprovalPolicyResult,
    CommerceStrategy,
    HumanApprovalDecision,
)
from commercepilot.models.review import ReviewInsight


class CommercePilotState(TypedDict):
    product_sku: str
    force_catalog_update: bool
    force_campaign_update: bool
    review_insight: ReviewInsight | None
    competitor_insight: CompetitorInsight | None
    strategy: CommerceStrategy | None
    campaign_requires_catalog_publish: NotRequired[bool]
    campaign_skip_reason: NotRequired[str]
    catalog_draft: CatalogDraft | None
    catalog_draft_id: UUID | None
    catalog_comparison: CatalogComparison | None
    catalog_approval_decision: HumanApprovalDecision | None
    catalog_publish_action_id: UUID | None
    catalog_execution_result: PublishCatalogUpdateResult | None
    campaign_evidence: CampaignEvidenceSet | None
    campaign_draft: CampaignDraft | None
    campaign_draft_id: UUID | None
    campaign_preview: CampaignLaunchPreview | None
    campaign_approval_decision: HumanApprovalDecision | None
    campaign_launch_action_id: UUID | None
    campaign_execution_result: LaunchCampaignResult | None
    approval_policy: ApprovalPolicyResult | None
    approval_decision: HumanApprovalDecision | None
    approved_action_ids: list[UUID]
    execution_results: list[UpdateProductPriceResult]
    review_error: str | None
    competitor_error: str | None
    catalog_error: str | None
    campaign_error: str | None
    error: str | None
