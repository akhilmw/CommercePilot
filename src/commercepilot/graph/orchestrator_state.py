from typing import TypedDict
from uuid import UUID

from commercepilot.mcp.client import (
    PublishCatalogUpdateResult,
    UpdateProductPriceResult,
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
    review_insight: ReviewInsight | None
    competitor_insight: CompetitorInsight | None
    strategy: CommerceStrategy | None
    catalog_draft: CatalogDraft | None
    catalog_draft_id: UUID | None
    catalog_comparison: CatalogComparison | None
    catalog_approval_decision: HumanApprovalDecision | None
    catalog_publish_action_id: UUID | None
    catalog_execution_result: PublishCatalogUpdateResult | None
    approval_policy: ApprovalPolicyResult | None
    approval_decision: HumanApprovalDecision | None
    approved_action_ids: list[UUID]
    execution_results: list[UpdateProductPriceResult]
    review_error: str | None
    competitor_error: str | None
    catalog_error: str | None
    error: str | None
