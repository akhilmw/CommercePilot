from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from commercepilot.db.models import Product, Review
from commercepilot.models.review import ReviewCreate
from commercepilot.services.review_ingestion import ingest_reviews


def make_review() -> ReviewCreate:
    return ReviewCreate(
        source_review_id="review-001",
        rating=4,
        title="Strong sound",
        body="The sound quality is excellent for daily listening.",
        verified_purchase=True,
        reviewed_at=datetime(2026, 11, 10, tzinfo=UTC),
    )


def test_ingest_reviews_creates_new_review() -> None:
    session = MagicMock(spec=Session)
    product = Product(
        id=uuid4(),
        sku="NOVA-AUDIO-001",
        name="NovaSound Pro",
        category="wireless-headphones",
        description="Wireless headphones for focused listening.",
        price="129.99",
    )
    session.scalar.side_effect = [product, None]

    result = ingest_reviews(session, product.sku, [make_review()])

    assert result.created == 1
    assert result.skipped == 0
    session.add.assert_called_once()
    added_review = session.add.call_args.args[0]
    assert isinstance(added_review, Review)
    assert added_review.product_id == product.id
    session.flush.assert_called_once()


def test_ingest_reviews_skips_existing_review() -> None:
    session = MagicMock(spec=Session)
    product = Product(
        id=uuid4(),
        sku="NOVA-AUDIO-001",
        name="NovaSound Pro",
        category="wireless-headphones",
        description="Wireless headphones for focused listening.",
        price="129.99",
    )
    session.scalar.side_effect = [product, MagicMock(spec=Review)]

    result = ingest_reviews(session, product.sku, [make_review()])

    assert result.created == 0
    assert result.skipped == 1
    session.add.assert_not_called()


def test_ingest_reviews_rejects_unknown_product() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None

    with pytest.raises(ValueError, match="Unknown product SKU"):
        ingest_reviews(session, "UNKNOWN-SKU", [make_review()])
