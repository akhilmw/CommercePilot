from sqlalchemy import func, select

from commercepilot.db.models import CompetitorPriceSnapshot, CompetitorProduct
from commercepilot.db.session import SessionLocal
from commercepilot.services.market_simulation import (
    calculate_price_change,
    insert_market_day,
    next_market_day,
)


def advance_market() -> None:
    with SessionLocal() as session:
        latest_observed_at = session.scalar(
            select(func.max(CompetitorPriceSnapshot.observed_at))
        )
        market_day = next_market_day(latest_observed_at)

        if market_day is None:
            print("The market simulation is already at its final day.")
            return

        products = {
            product.competitor_sku: product
            for product in session.scalars(select(CompetitorProduct)).all()
        }
        previous_prices = {
            market_price.competitor_sku: session.scalar(
                select(CompetitorPriceSnapshot.price)
                .where(
                    CompetitorPriceSnapshot.competitor_product_id
                    == products[market_price.competitor_sku].id,
                    CompetitorPriceSnapshot.observed_at < market_day.observed_at,
                )
                .order_by(CompetitorPriceSnapshot.observed_at.desc())
                .limit(1)
            )
            for market_price in market_day.prices
        }

        created = insert_market_day(session, market_day)
        session.commit()

        print(f"Advanced market simulation to Day {market_day.day}.")
        print(f"Price snapshots created: {created}")

        for market_price in market_day.prices:
            old_price = previous_prices[market_price.competitor_sku]
            if old_price is None:
                print(
                    f"{market_price.competitor_sku}: "
                    f"initial price {market_price.price}"
                )
                continue

            change = calculate_price_change(old_price, market_price.price)
            print(
                f"{market_price.competitor_sku}: "
                f"{old_price} -> {market_price.price} ({change}%)"
            )


if __name__ == "__main__":
    advance_market()
