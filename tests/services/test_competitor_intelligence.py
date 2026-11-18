from decimal import Decimal

import pytest

from commercepilot.models.enums import PriceChangeType
from commercepilot.services.competitor_intelligence import classify_price_change


@pytest.mark.parametrize(
    ("previous_price", "current_price", "expected"),
    [
        (None, Decimal("109.99"), PriceChangeType.INITIAL),
        (
            Decimal("139.99"),
            Decimal("109.99"),
            PriceChangeType.DECREASED,
        ),
        (
            Decimal("109.99"),
            Decimal("109.99"),
            PriceChangeType.UNCHANGED,
        ),
        (
            Decimal("109.99"),
            Decimal("119.99"),
            PriceChangeType.INCREASED,
        ),
    ],
)
def test_classify_price_change(
    previous_price: Decimal | None,
    current_price: Decimal,
    expected: PriceChangeType,
) -> None:
    assert classify_price_change(previous_price, current_price) is expected
