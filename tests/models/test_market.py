from datetime import UTC, datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from commercepilot.models.market import MarketSnapshotCreate


def test_market_snapshot_normalizes_competitor_sku() -> None:
    request = MarketSnapshotCreate(
        competitor_sku="ap-cm2",
        price=Decimal("89.99"),
        observed_at=datetime.now(UTC),
    )

    assert request.competitor_sku == "AP-CM2"


def test_market_snapshot_requires_timezone() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        MarketSnapshotCreate(
            competitor_sku="AP-CM2",
            price=Decimal("89.99"),
            observed_at=datetime(2026, 11, 22, 12),
        )
