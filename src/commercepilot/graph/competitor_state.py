from typing import TypedDict

from commercepilot.models.competitor import (
    CompetitorEvidenceSet,
    CompetitorInsight,
)


class CompetitorAgentState(TypedDict):
    product_sku: str
    evidence: CompetitorEvidenceSet | None
    insight: CompetitorInsight | None
    error: str | None
