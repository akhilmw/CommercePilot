from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from commercepilot.models.competitor import (
    CompetitiveRecommendation,
    CompetitorEvidenceSet,
    CompetitorFinding,
    CompetitorInsight,
    CompetitorPriceChange,
)
from commercepilot.models.enums import (
    CompetitiveThreatLevel,
    ImprovementPriority,
    PriceChangeType,
)
from commercepilot.services.competitor_analysis import (
    analyze_competitor_evidence,
    validate_competitor_insight_evidence,
)


def make_evidence() -> CompetitorEvidenceSet:
    product_id = uuid4()
    return CompetitorEvidenceSet(
        product_id=product_id,
        product_sku="NOVA-AUDIO-001",
        product_name="NovaSound Pro",
        our_price=Decimal("129.99"),
        currency="USD",
        price_changes=[
            CompetitorPriceChange(
                competitor_product_id=uuid4(),
                current_snapshot_id=uuid4(),
                previous_snapshot_id=uuid4(),
                competitor_name="AudioPeak",
                competitor_product_name="ComfortMax 2",
                previous_price=Decimal("139.99"),
                current_price=Decimal("109.99"),
                change_type=PriceChangeType.DECREASED,
                change_amount=Decimal("-30.00"),
                change_percent=Decimal("-21.43"),
                our_price=Decimal("129.99"),
                price_difference_from_ours=Decimal("-20.00"),
                is_cheaper_than_ours=True,
                promotion="Limited-time 21% discount",
                observed_at=datetime(2026, 11, 12, 9, tzinfo=UTC),
            )
        ],
    )


def make_insight(evidence: CompetitorEvidenceSet) -> CompetitorInsight:
    change = evidence.price_changes[0]
    previous_snapshot_id = change.previous_snapshot_id
    assert previous_snapshot_id is not None

    return CompetitorInsight(
        product_sku=evidence.product_sku,
        our_price=evidence.our_price,
        currency=evidence.currency,
        overall_threat_level=CompetitiveThreatLevel.HIGH,
        market_summary=(
            "AudioPeak created significant pricing pressure by moving below "
            "NovaSound Pro."
        ),
        findings=[
            CompetitorFinding(
                competitor_product_id=change.competitor_product_id,
                competitor_name=change.competitor_name,
                threat_level=CompetitiveThreatLevel.HIGH,
                summary=(
                    "AudioPeak reduced its price by 21.43% and is now twenty "
                    "dollars cheaper."
                ),
                evidence_snapshot_ids=[
                    previous_snapshot_id,
                    change.current_snapshot_id,
                ],
            )
        ],
        recommended_actions=[
            CompetitiveRecommendation(
                recommendation="Review NovaSound Pro's pricing position.",
                rationale=(
                    "A comparable product is currently twenty dollars cheaper."
                ),
                priority=ImprovementPriority.HIGH,
                evidence_snapshot_ids=[change.current_snapshot_id],
            )
        ],
        confidence=0.9,
    )


def test_analyze_competitor_evidence_returns_validated_output() -> None:
    evidence = make_evidence()
    insight = make_insight(evidence)
    client = MagicMock()
    client.responses.parse.return_value.output_parsed = insight

    result = analyze_competitor_evidence(evidence, client, "test-model")

    assert result is insight
    request = client.responses.parse.call_args.kwargs
    assert request["model"] == "test-model"
    assert request["text_format"] is CompetitorInsight


def test_validate_competitor_insight_rejects_unknown_snapshot() -> None:
    evidence = make_evidence()
    insight = make_insight(evidence)
    insight.findings[0].evidence_snapshot_ids = [uuid4()]

    with pytest.raises(ValueError, match="unknown snapshot IDs"):
        validate_competitor_insight_evidence(insight, evidence)


def test_validate_competitor_insight_rejects_wrong_competitor_name() -> None:
    evidence = make_evidence()
    insight = make_insight(evidence)
    insight.findings[0].competitor_name = "Wrong Company"

    with pytest.raises(ValueError, match="name does not match"):
        validate_competitor_insight_evidence(insight, evidence)
