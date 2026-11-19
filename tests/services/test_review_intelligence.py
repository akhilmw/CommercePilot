from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from commercepilot.db.models import Product, Review
from commercepilot.services.review_intelligence import load_review_evidence


def make_product() -> Product:
    return Product(
        id=uuid4(),
        sku="NOVA-AUDIO-001",
        name="NovaSound Pro",
        category="wireless-headphones",
        description="Wireless headphones for focused listening.",
        price=Decimal("129.99"),
    )


def make_review(
    product_id: object,
    source_review_id: str,
    rating: int,
    reviewed_at: datetime,
    *,
    verified_purchase: bool,
) -> Review:
    return Review(
        id=uuid4(),
        product_id=product_id,
        source_review_id=source_review_id,
        source="synthetic-novacart",
        rating=rating,
        title=f"Review {source_review_id}",
        body="This review contains enough evidence for the test.",
        verified_purchase=verified_purchase,
        reviewed_at=reviewed_at,
        created_at=reviewed_at,
    )


def test_load_review_evidence_calculates_statistics() -> None:
    session = MagicMock(spec=Session)
    product = make_product()
    reviews = [
        make_review(
            product.id,
            "review-001",
            5,
            datetime(2026, 11, 1, tzinfo=UTC),
            verified_purchase=True,
        ),
        make_review(
            product.id,
            "review-002",
            3,
            datetime(2026, 11, 2, tzinfo=UTC),
            verified_purchase=False,
        ),
        make_review(
            product.id,
            "review-003",
            2,
            datetime(2026, 11, 3, tzinfo=UTC),
            verified_purchase=True,
        ),
    ]
    session.scalar.return_value = product
    session.scalars.return_value.all.return_value = reviews

    evidence = load_review_evidence(session, product.sku)

    assert evidence.review_count == 3
    assert evidence.average_rating == 3.33
    assert evidence.rating_distribution == {1: 0, 2: 1, 3: 1, 4: 0, 5: 1}
    assert evidence.verified_purchase_count == 2
    assert evidence.reviewed_from == reviews[0].reviewed_at
    assert evidence.reviewed_to == reviews[-1].reviewed_at


def test_load_review_evidence_handles_product_without_reviews() -> None:
    session = MagicMock(spec=Session)
    product = make_product()
    session.scalar.return_value = product
    session.scalars.return_value.all.return_value = []

    evidence = load_review_evidence(session, product.sku)

    assert evidence.review_count == 0
    assert evidence.average_rating == 0.0
    assert evidence.rating_distribution == {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    assert evidence.reviewed_from is None
    assert evidence.reviewed_to is None


def test_load_review_evidence_rejects_unknown_product() -> None:
    session = MagicMock(spec=Session)
    session.scalar.return_value = None

    with pytest.raises(ValueError, match="Unknown product SKU"):
        load_review_evidence(session, "UNKNOWN-SKU")
