from scripts.seed_reviews import PRODUCT_SKU, SYNTHETIC_REVIEWS


def test_synthetic_review_dataset_is_complete() -> None:
    assert PRODUCT_SKU == "NOVA-AUDIO-001"
    assert len(SYNTHETIC_REVIEWS) == 25
    assert len({review.source_review_id for review in SYNTHETIC_REVIEWS}) == 25


def test_synthetic_review_dataset_contains_mixed_feedback() -> None:
    ratings = {review.rating for review in SYNTHETIC_REVIEWS}
    combined_text = " ".join(review.body.lower() for review in SYNTHETIC_REVIEWS)

    assert ratings == {2, 3, 4, 5}
    assert "battery" in combined_text
    assert "microphone" in combined_text
    assert "uncomfortable" in combined_text
    assert "bluetooth" in combined_text
