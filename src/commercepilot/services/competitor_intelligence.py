from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from commercepilot.db.models import (
    Competitor,
    CompetitorPriceSnapshot,
    CompetitorProduct,
    Product,
)
from commercepilot.models.competitor import CompetitorPriceChange
from commercepilot.models.enums import PriceChangeType
from commercepilot.services.market_simulation import calculate_price_change


def classify_price_change(
    previous_price: Decimal | None,
    current_price: Decimal,
) -> PriceChangeType:
    if previous_price is None:
        return PriceChangeType.INITIAL
    if current_price < previous_price:
        return PriceChangeType.DECREASED
    if current_price > previous_price:
        return PriceChangeType.INCREASED
    return PriceChangeType.UNCHANGED


def analyze_competitor_prices(
    session: Session,
    product_sku: str,
) -> list[CompetitorPriceChange]:
    product = session.scalar(select(Product).where(Product.sku == product_sku))
    if product is None:
        raise ValueError(f"Unknown product SKU: {product_sku}")

    rows = session.execute(
        select(Competitor, CompetitorProduct, CompetitorPriceSnapshot)
        .join(
            CompetitorProduct,
            CompetitorProduct.competitor_id == Competitor.id,
        )
        .join(
            CompetitorPriceSnapshot,
            CompetitorPriceSnapshot.competitor_product_id
            == CompetitorProduct.id,
        )
        .where(CompetitorProduct.product_id == product.id)
        .order_by(
            CompetitorProduct.id,
            CompetitorPriceSnapshot.observed_at.desc(),
        )
    ).all()

    snapshots_by_product: dict[
        object,
        list[tuple[Competitor, CompetitorProduct, CompetitorPriceSnapshot]],
    ] = defaultdict(list)
    for competitor, competitor_product, snapshot in rows:
        snapshots_by_product[competitor_product.id].append(
            (competitor, competitor_product, snapshot)
        )

    changes: list[CompetitorPriceChange] = []
    for product_snapshots in snapshots_by_product.values():
        competitor, competitor_product, current = product_snapshots[0]
        previous = product_snapshots[1][2] if len(product_snapshots) > 1 else None
        previous_price = previous.price if previous is not None else None
        change_amount = (
            current.price - previous_price
            if previous_price is not None
            else Decimal("0.00")
        )
        change_percent = (
            calculate_price_change(previous_price, current.price)
            if previous_price is not None
            else Decimal("0.00")
        )
        price_difference = current.price - product.price

        changes.append(
            CompetitorPriceChange(
                competitor_product_id=competitor_product.id,
                competitor_name=competitor.name,
                competitor_product_name=competitor_product.name,
                previous_price=previous_price,
                current_price=current.price,
                change_type=classify_price_change(
                    previous_price,
                    current.price,
                ),
                change_amount=change_amount,
                change_percent=change_percent,
                our_price=product.price,
                price_difference_from_ours=price_difference,
                is_cheaper_than_ours=current.price < product.price,
                promotion=current.promotion,
                observed_at=current.observed_at,
            )
        )

    return sorted(changes, key=lambda change: change.competitor_name)
