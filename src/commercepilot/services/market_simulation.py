from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from commercepilot.db.models import CompetitorPriceSnapshot, CompetitorProduct


@dataclass(frozen=True)
class MarketPrice:
    competitor_sku: str
    price: Decimal
    promotion: str | None = None


@dataclass(frozen=True)
class MarketDay:
    day: int
    observed_at: datetime
    prices: tuple[MarketPrice, ...]


MARKET_DAYS = (
    MarketDay(
        day=1,
        observed_at=datetime(2026, 11, 10, 9, tzinfo=UTC),
        prices=(
            MarketPrice("AP-CM2", Decimal("139.99")),
            MarketPrice("SF-QCX", Decimal("149.99")),
            MarketPrice("CW-SG", Decimal("119.99")),
            MarketPrice("PL-PT4", Decimal("239.99")),
            MarketPrice("KN-MOS", Decimal("269.99")),
            MarketPrice("WS-VBP", Decimal("219.99")),
            MarketPrice("BC-BH", Decimal("189.99")),
            MarketPrice("CFW-CT", Decimal("159.99")),
            MarketPrice("BF-MP", Decimal("169.99")),
        ),
    ),
    MarketDay(
        day=2,
        observed_at=datetime(2026, 11, 12, 9, tzinfo=UTC),
        prices=(
            MarketPrice(
                "AP-CM2",
                Decimal("109.99"),
                "Limited-time 21% discount",
            ),
            MarketPrice("SF-QCX", Decimal("149.99")),
            MarketPrice("CW-SG", Decimal("119.99")),
            MarketPrice(
                "PL-PT4",
                Decimal("199.99"),
                "Holiday fitness promotion",
            ),
            MarketPrice("KN-MOS", Decimal("269.99")),
            MarketPrice("WS-VBP", Decimal("209.99")),
            MarketPrice("BC-BH", Decimal("189.99")),
            MarketPrice("CFW-CT", Decimal("159.99")),
            MarketPrice(
                "BF-MP",
                Decimal("139.99"),
                "Limited-time kitchen sale",
            ),
        ),
    ),
    MarketDay(
        day=3,
        observed_at=datetime(2026, 11, 15, 9, tzinfo=UTC),
        prices=(
            MarketPrice(
                "AP-CM2",
                Decimal("109.99"),
                "Limited-time 21% discount",
            ),
            MarketPrice("SF-QCX", Decimal("149.99")),
            MarketPrice(
                "CW-SG",
                Decimal("114.99"),
                "Weekend promotion",
            ),
            MarketPrice("PL-PT4", Decimal("219.99")),
            MarketPrice(
                "KN-MOS",
                Decimal("249.99"),
                "Member pricing",
            ),
            MarketPrice("WS-VBP", Decimal("209.99")),
            MarketPrice(
                "BC-BH",
                Decimal("169.99"),
                "Coffee week promotion",
            ),
            MarketPrice("CFW-CT", Decimal("159.99")),
            MarketPrice("BF-MP", Decimal("139.99")),
        ),
    ),
)


def calculate_price_change(
    previous_price: Decimal,
    current_price: Decimal,
) -> Decimal:
    if previous_price == 0:
        return Decimal("0.00")

    return (
        ((current_price - previous_price) / previous_price) * Decimal("100")
    ).quantize(Decimal("0.01"))


def next_market_day(latest_observed_at: datetime | None) -> MarketDay | None:
    for market_day in MARKET_DAYS:
        if latest_observed_at is None or market_day.observed_at > latest_observed_at:
            return market_day

    return None


def insert_market_day(session: Session, market_day: MarketDay) -> int:
    created = 0

    for market_price in market_day.prices:
        competitor_product = session.scalar(
            select(CompetitorProduct).where(
                CompetitorProduct.competitor_sku == market_price.competitor_sku
            )
        )
        if competitor_product is None:
            raise ValueError(
                f"Unknown competitor SKU: {market_price.competitor_sku}"
            )

        existing_snapshot = session.scalar(
            select(CompetitorPriceSnapshot).where(
                CompetitorPriceSnapshot.competitor_product_id
                == competitor_product.id,
                CompetitorPriceSnapshot.observed_at == market_day.observed_at,
            )
        )
        if existing_snapshot is not None:
            continue

        session.add(
            CompetitorPriceSnapshot(
                competitor_product_id=competitor_product.id,
                price=market_price.price,
                currency="USD",
                promotion=market_price.promotion,
                observed_at=market_day.observed_at,
            )
        )
        created += 1

    return created
