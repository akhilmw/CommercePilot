from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from commercepilot.models.enums import ReviewSentiment
from commercepilot.models.review import (
    ReviewEvidenceSet,
    ReviewInsight,
    ReviewRead,
    ReviewTheme,
)
from commercepilot.services.review_analysis import (
    analyze_review_evidence,
    validate_review_insight_evidence,
)


def make_evidence() -> ReviewEvidenceSet:
    product_id = uuid4()
    review = ReviewRead(
        id=uuid4(),
        product_id=product_id,
        source_review_id="review-001",
        source="synthetic-novacart",
        rating=5,
        title="Excellent sound",
        body="The sound is detailed and balanced for everyday listening.",
        verified_purchase=True,
        reviewed_at=datetime(2026, 11, 1, tzinfo=UTC),
        created_at=datetime(2026, 11, 1, tzinfo=UTC),
    )
    return ReviewEvidenceSet(
        product_id=product_id,
        product_sku="NOVA-AUDIO-001",
        product_name="NovaSound Pro",
        review_count=1,
        average_rating=5.0,
        rating_distribution={1: 0, 2: 0, 3: 0, 4: 0, 5: 1},
        verified_purchase_count=1,
        reviewed_from=review.reviewed_at,
        reviewed_to=review.reviewed_at,
        reviews=[review],
    )


def make_insight(evidence: ReviewEvidenceSet) -> ReviewInsight:
    return ReviewInsight(
        product_sku=evidence.product_sku,
        overall_sentiment=ReviewSentiment.POSITIVE,
        executive_summary=(
            "The available customer evidence strongly praises the product's "
            "sound quality."
        ),
        strengths=[
            ReviewTheme(
                theme="sound quality",
                summary="The reviewer describes detailed and balanced audio.",
                evidence_review_ids=[evidence.reviews[0].id],
            )
        ],
        complaints=[],
        requested_improvements=[],
        confidence=0.9,
    )


def test_analyze_review_evidence_returns_validated_output() -> None:
    evidence = make_evidence()
    insight = make_insight(evidence)
    client = MagicMock()
    client.responses.parse.return_value.output_parsed = insight

    result = analyze_review_evidence(evidence, client, "test-model")

    assert result is insight
    client.responses.parse.assert_called_once()
    request = client.responses.parse.call_args.kwargs
    assert request["model"] == "test-model"
    assert request["text_format"] is ReviewInsight


def test_validate_review_insight_rejects_unknown_citation() -> None:
    evidence = make_evidence()
    insight = make_insight(evidence)
    insight.strengths[0].evidence_review_ids = [uuid4()]

    with pytest.raises(ValueError, match="unknown review IDs"):
        validate_review_insight_evidence(insight, evidence)


def test_analyze_review_evidence_rejects_empty_evidence() -> None:
    evidence = make_evidence().model_copy(
        update={
            "review_count": 0,
            "reviews": [],
            "reviewed_from": None,
            "reviewed_to": None,
        }
    )

    with pytest.raises(ValueError, match="No reviews"):
        analyze_review_evidence(evidence, MagicMock(), "test-model")
