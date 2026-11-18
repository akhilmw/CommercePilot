from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from commercepilot.models.competitor import CompetitorPriceSnapshotCreate


def test_price_snapshot_normalizes_currency() -> None:
    snapshot = CompetitorPriceSnapshotCreate(
        competitor_product_id=uuid4(),
        price=Decimal("109.99"),
        currency="usd",
        observed_at=datetime(2026, 11, 12, tzinfo=UTC),
    )

    assert snapshot.currency == "USD"


def test_price_snapshot_rejects_negative_price() -> None:
    with pytest.raises(ValidationError):
        CompetitorPriceSnapshotCreate(
            competitor_product_id=uuid4(),
            price=Decimal("-0.01"),
            observed_at=datetime(2026, 11, 12, tzinfo=UTC),
        )
