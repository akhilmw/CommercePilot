from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from commercepilot.models.review import ReviewCreate


def test_review_create_normalizes_text() -> None:
    review = ReviewCreate(
        source_review_id="  review-001  ",
        source="  novacart  ",
        rating=4,
        title="  Strong sound  ",
        body="  The sound quality is excellent for daily listening.  ",
        verified_purchase=True,
        reviewed_at=datetime(2026, 11, 10, tzinfo=UTC),
    )

    assert review.source_review_id == "review-001"
    assert review.source == "novacart"
    assert review.title == "Strong sound"
    assert review.body == "The sound quality is excellent for daily listening."


@pytest.mark.parametrize("rating", [0, 6])
def test_review_create_rejects_invalid_rating(rating: int) -> None:
    with pytest.raises(ValidationError):
        ReviewCreate(
            source_review_id="review-001",
            rating=rating,
            body="This review body is long enough.",
            reviewed_at=datetime(2026, 11, 10, tzinfo=UTC),
        )
