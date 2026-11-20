from typing import TypedDict

from commercepilot.models.campaign import CampaignDraft, CampaignEvidenceSet
from commercepilot.models.competitor import CompetitorInsight
from commercepilot.models.orchestration import CommerceStrategy
from commercepilot.models.review import ReviewInsight


class CampaignAgentState(TypedDict):
    product_sku: str
    review_insight: ReviewInsight | None
    competitor_insight: CompetitorInsight | None
    strategy: CommerceStrategy | None
    evidence: CampaignEvidenceSet | None
    draft: CampaignDraft | None
    error: str | None
