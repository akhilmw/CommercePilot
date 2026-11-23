from scripts.seed_reviews import (
    NOVA_BREW_REVIEWS,
    NOVA_FIT_REVIEWS,
    PRODUCT_SKU,
    REVIEW_DATASETS,
    SYNTHETIC_REVIEWS,
)


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


def test_each_seed_product_has_unique_mixed_reviews() -> None:
    assert set(REVIEW_DATASETS) == {
        "NOVA-AUDIO-001",
        "NOVA-WEAR-001",
        "NOVA-HOME-001",
    }
    all_review_ids = {
        review.source_review_id
        for reviews in REVIEW_DATASETS.values()
        for review in reviews
    }
    assert len(all_review_ids) == sum(map(len, REVIEW_DATASETS.values()))
    assert {review.rating for review in NOVA_FIT_REVIEWS} == {2, 3, 4, 5}
    assert {review.rating for review in NOVA_BREW_REVIEWS} == {2, 3, 4, 5}
