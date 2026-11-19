from decimal import Decimal
from uuid import uuid4

import pytest

from commercepilot.models.competitor import (
    CompetitorFinding,
    CompetitorInsight,
)
from commercepilot.models.enums import (
    ActionType,
    CompetitiveThreatLevel,
    ImprovementPriority,
    ReviewSentiment,
    SourceAgent,
)
from commercepilot.models.orchestration import (
    ActionProposal,
    CommerceStrategy,
)
from commercepilot.models.review import ReviewInsight, ReviewTheme
from commercepilot.services.strategy_synthesis import (
    validate_strategy_evidence,
)


def make_insights() -> tuple[ReviewInsight, CompetitorInsight]:
    review_id = uuid4()
    snapshot_id = uuid4()
    review_insight = ReviewInsight(
        product_sku="NOVA-AUDIO-001",
        overall_sentiment=ReviewSentiment.MIXED,
        executive_summary=(
            "Customers praise sound quality but report microphone problems."
        ),
        strengths=[
            ReviewTheme(
                theme="sound quality",
                summary="Customers repeatedly praise detailed and balanced sound.",
                evidence_review_ids=[review_id],
            )
        ],
        complaints=[],
        requested_improvements=[],
        confidence=0.8,
    )
    competitor_insight = CompetitorInsight(
        product_sku="NOVA-AUDIO-001",
        our_price=Decimal("129.99"),
        currency="USD",
        overall_threat_level=CompetitiveThreatLevel.HIGH,
        market_summary=(
            "AudioPeak is currently cheaper and creates pricing pressure."
        ),
        findings=[
            CompetitorFinding(
                competitor_product_id=uuid4(),
                competitor_name="AudioPeak",
                threat_level=CompetitiveThreatLevel.HIGH,
                summary="AudioPeak is currently twenty dollars cheaper.",
                evidence_snapshot_ids=[snapshot_id],
            )
        ],
        recommended_actions=[],
        confidence=0.8,
    )
    return review_insight, competitor_insight


def make_strategy(
    review_insight: ReviewInsight,
    competitor_insight: CompetitorInsight,
) -> CommerceStrategy:
    review_id = review_insight.strengths[0].evidence_review_ids[0]
    snapshot_id = competitor_insight.findings[0].evidence_snapshot_ids[0]
    return CommerceStrategy(
        product_sku="NOVA-AUDIO-001",
        situation_summary=(
            "NovaSound Pro has strong customer-perceived audio quality while "
            "facing material price competition."
        ),
        strategic_objectives=[
            "Defend conversion while preserving the product's value position."
        ],
        action_proposals=[
            ActionProposal(
                action_type=ActionType.DRAFT_CAMPAIGN,
                title="Draft a value-focused campaign",
                description=(
                    "Create campaign copy emphasizing sound quality and value."
                ),
                rationale=(
                    "Review and competitor evidence support differentiated "
                    "positioning."
                ),
                priority=ImprovementPriority.HIGH,
                source_agents=[
                    SourceAgent.REVIEW,
                    SourceAgent.COMPETITOR,
                ],
                evidence_ids=[review_id, snapshot_id],
            )
        ],
        confidence=0.85,
    )


def test_validate_strategy_accepts_cross_agent_evidence() -> None:
    review_insight, competitor_insight = make_insights()
    strategy = make_strategy(review_insight, competitor_insight)

    validate_strategy_evidence(
        strategy,
        review_insight,
        competitor_insight,
    )


def test_validate_strategy_rejects_missing_source_agent() -> None:
    review_insight, competitor_insight = make_insights()
    strategy = make_strategy(review_insight, competitor_insight)
    strategy.action_proposals[0].source_agents = [SourceAgent.REVIEW]

    with pytest.raises(ValueError, match="Competitor Agent"):
        validate_strategy_evidence(
            strategy,
            review_insight,
            competitor_insight,
        )


def test_validate_strategy_rejects_unknown_evidence() -> None:
    review_insight, competitor_insight = make_insights()
    strategy = make_strategy(review_insight, competitor_insight)
    strategy.action_proposals[0].evidence_ids = [uuid4()]

    with pytest.raises(ValueError, match="unknown evidence IDs"):
        validate_strategy_evidence(
            strategy,
            review_insight,
            competitor_insight,
        )
