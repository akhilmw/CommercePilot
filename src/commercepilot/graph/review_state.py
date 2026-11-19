from typing import TypedDict

from commercepilot.models.review import ReviewEvidenceSet, ReviewInsight


class ReviewAgentState(TypedDict):
    product_sku: str
    evidence: ReviewEvidenceSet | None
    insight: ReviewInsight | None
    error: str | None
