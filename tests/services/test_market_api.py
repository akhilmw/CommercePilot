from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from commercepilot.db.models import (
    Competitor,
    CompetitorPriceSnapshot,
    CompetitorProduct,
    Product,
)
from commercepilot.models.market import MarketSnapshotCreate
from commercepilot.services.market_api import (
    MarketSnapshotConflictError,
    create_market_snapshot,
)


def make_market_records() -> tuple[
    Product,
    CompetitorProduct,
    CompetitorPriceSnapshot,
]:
    product = Product(
        id=uuid4(),
        sku="NOVA-AUDIO-001",
        name="NovaSound Pro",
        category="wireless-headphones",
        description="Wireless over-ear headphones.",
        price=Decimal("99.99"),
        currency="USD",
    )
    competitor = Competitor(id=uuid4(), name="AudioPeak", slug="audiopeak")
    competitor_product = CompetitorProduct(
        id=uuid4(),
        competitor=competitor,
        product_id=product.id,
        competitor_sku="AP-CM2",
        name="ComfortMax 2",
    )
    previous = CompetitorPriceSnapshot(
        id=uuid4(),
        competitor_product_id=competitor_product.id,
        price=Decimal("109.99"),
        currency="USD",
        observed_at=datetime.now(UTC) - timedelta(days=1),
    )
    return product, competitor_product, previous


def test_create_market_snapshot_reports_price_drop() -> None:
    session = MagicMock(spec=Session)
    product, competitor_product, previous = make_market_records()
    session.scalar.side_effect = [product, competitor_product, previous]
    request = MarketSnapshotCreate(
        competitor_sku="AP-CM2",
        price=Decimal("89.99"),
        promotion="Flash sale",
        observed_at=datetime.now(UTC),
    )

    result = create_market_snapshot(session, product.sku, request)

    assert result.previous_price == Decimal("109.99")
    assert result.current_price == Decimal("89.99")
    assert result.change_percent == Decimal("-18.18")
    assert result.is_cheaper_than_ours is True
    session.add.assert_called_once()
    session.commit.assert_called_once()


def test_create_market_snapshot_rejects_backdated_observation() -> None:
    session = MagicMock(spec=Session)
    product, competitor_product, previous = make_market_records()
    session.scalar.side_effect = [product, competitor_product, previous]

    with pytest.raises(MarketSnapshotConflictError):
        create_market_snapshot(
            session,
            product.sku,
            MarketSnapshotCreate(
                competitor_sku="AP-CM2",
                price=Decimal("89.99"),
                observed_at=previous.observed_at,
            ),
        )

    session.add.assert_not_called()
