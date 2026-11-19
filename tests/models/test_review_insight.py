from uuid import uuid4

import pytest
from pydantic import ValidationError

from commercepilot.models.enums import ImprovementPriority, ReviewSentiment
from commercepilot.models.review import (
    RequestedImprovement,
    ReviewInsight,
    ReviewTheme,
)


def make_insight() -> ReviewInsight:
    comfort_review_id = uuid4()
    microphone_review_id = uuid4()

    return ReviewInsight(
        product_sku="nova-audio-001",
        overall_sentiment=ReviewSentiment.MIXED,
        executive_summary=(
            "Customers value the audio and battery but repeatedly report "
            "comfort and microphone problems."
        ),
        strengths=[
            ReviewTheme(
                theme="sound quality",
                summary="Customers consistently describe clear and balanced audio.",
                evidence_review_ids=[comfort_review_id],
            )
        ],
        complaints=[
            ReviewTheme(
                theme="microphone quality",
                summary="Callers report distant, compressed, or muffled speech.",
                evidence_review_ids=[microphone_review_id],
            )
        ],
        requested_improvements=[
            RequestedImprovement(
                recommendation="Improve microphone clarity for work calls.",
                rationale="Multiple reviewers cannot rely on the built-in microphone.",
                priority=ImprovementPriority.HIGH,
                evidence_review_ids=[microphone_review_id],
            )
        ],
        confidence=0.88,
    )


def test_review_insight_validates_structured_agent_output() -> None:
    insight = make_insight()

    assert insight.product_sku == "NOVA-AUDIO-001"
    assert insight.overall_sentiment is ReviewSentiment.MIXED
    assert insight.confidence == 0.88


def test_review_theme_requires_evidence() -> None:
    with pytest.raises(ValidationError):
        ReviewTheme(
            theme="comfort",
            summary="Customers report discomfort during extended listening.",
            evidence_review_ids=[],
        )


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_review_insight_rejects_invalid_confidence(confidence: float) -> None:
    insight = make_insight().model_dump()
    insight["confidence"] = confidence

    with pytest.raises(ValidationError):
        ReviewInsight.model_validate(insight)
