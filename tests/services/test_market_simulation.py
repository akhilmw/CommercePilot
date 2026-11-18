from datetime import UTC, datetime
from decimal import Decimal

from commercepilot.services.market_simulation import (
    MARKET_DAYS,
    calculate_price_change,
    next_market_day,
)


def test_calculate_price_change_detects_audiopeak_drop() -> None:
    change = calculate_price_change(
        Decimal("139.99"),
        Decimal("109.99"),
    )

    assert change == Decimal("-21.43")


def test_next_market_day_returns_first_day_without_history() -> None:
    assert next_market_day(None) == MARKET_DAYS[0]


def test_next_market_day_returns_day_after_latest_snapshot() -> None:
    latest = datetime(2026, 11, 10, 9, tzinfo=UTC)

    assert next_market_day(latest) == MARKET_DAYS[1]


def test_next_market_day_returns_none_after_final_day() -> None:
    latest = datetime(2026, 11, 15, 9, tzinfo=UTC)

    assert next_market_day(latest) is None
