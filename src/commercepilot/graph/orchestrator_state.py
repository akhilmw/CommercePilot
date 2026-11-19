from typing import TypedDict

from commercepilot.models.competitor import CompetitorInsight
from commercepilot.models.orchestration import (
    ApprovalPolicyResult,
    CommerceStrategy,
    HumanApprovalDecision,
)
from commercepilot.models.review import ReviewInsight


class CommercePilotState(TypedDict):
    product_sku: str
    review_insight: ReviewInsight | None
    competitor_insight: CompetitorInsight | None
    strategy: CommerceStrategy | None
    approval_policy: ApprovalPolicyResult | None
    approval_decision: HumanApprovalDecision | None
    review_error: str | None
    competitor_error: str | None
    error: str | None
