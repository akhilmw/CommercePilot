from typing import TypedDict

from commercepilot.models.catalog import CatalogDraft, CatalogEvidenceSet
from commercepilot.models.competitor import CompetitorInsight
from commercepilot.models.review import ReviewInsight


class CatalogAgentState(TypedDict):
    product_sku: str
    review_insight: ReviewInsight | None
    competitor_insight: CompetitorInsight | None
    evidence: CatalogEvidenceSet | None
    draft: CatalogDraft | None
    error: str | None
