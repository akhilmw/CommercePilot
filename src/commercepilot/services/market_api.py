from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from commercepilot.db.models import (
    CompetitorPriceSnapshot,
    CompetitorProduct,
    Product,
)
from commercepilot.models.market import (
    MarketCompetitorView,
    MarketOverview,
    MarketSnapshotCreate,
    MarketSnapshotResult,
)
from commercepilot.services.competitor_intelligence import (
    classify_price_change,
    load_competitor_evidence,
)
from commercepilot.services.market_simulation import calculate_price_change


class MarketProductNotFoundError(ValueError):
    pass


class MarketCompetitorNotFoundError(ValueError):
    pass


class MarketSnapshotConflictError(ValueError):
    pass


def get_market_overview(session: Session, product_sku: str) -> MarketOverview:
    product = session.scalar(select(Product).where(Product.sku == product_sku))
    if product is None:
        raise MarketProductNotFoundError(f"Product not found: {product_sku}")

    competitor_products = list(
        session.scalars(
            select(CompetitorProduct)
            .options(joinedload(CompetitorProduct.competitor))
            .where(CompetitorProduct.product_id == product.id)
            .order_by(CompetitorProduct.name)
        )
    )
    evidence = load_competitor_evidence(session, product.sku)
    changes = {
        change.competitor_product_id: change for change in evidence.price_changes
    }
    competitors = []
    for competitor_product in competitor_products:
        change = changes.get(competitor_product.id)
        if change is None:
            continue
        competitors.append(
            MarketCompetitorView(
                competitor_product_id=competitor_product.id,
                competitor_sku=competitor_product.competitor_sku,
                competitor_name=competitor_product.competitor.name,
                competitor_product_name=competitor_product.name,
                current_snapshot_id=change.current_snapshot_id,
                previous_snapshot_id=change.previous_snapshot_id,
                previous_price=change.previous_price,
                current_price=change.current_price,
                currency=product.currency,
                change_type=change.change_type,
                change_amount=change.change_amount,
                change_percent=change.change_percent,
                promotion=change.promotion,
                observed_at=change.observed_at,
                price_difference_from_ours=change.price_difference_from_ours,
                is_cheaper_than_ours=change.is_cheaper_than_ours,
            )
        )
    return MarketOverview(
        product_id=product.id,
        product_sku=product.sku,
        product_name=product.name,
        our_price=product.price,
        currency=product.currency,
        competitors=competitors,
    )


def create_market_snapshot(
    session: Session,
    product_sku: str,
    request: MarketSnapshotCreate,
) -> MarketSnapshotResult:
    product = session.scalar(select(Product).where(Product.sku == product_sku))
    if product is None:
        raise MarketProductNotFoundError(f"Product not found: {product_sku}")

    competitor_product = session.scalar(
        select(CompetitorProduct)
        .where(
            CompetitorProduct.product_id == product.id,
            CompetitorProduct.competitor_sku == request.competitor_sku,
        )
        .with_for_update()
    )
    if competitor_product is None:
        raise MarketCompetitorNotFoundError(
            f"Competitor product not found for {product_sku}: "
            f"{request.competitor_sku}"
        )

    previous = session.scalar(
        select(CompetitorPriceSnapshot)
        .where(
            CompetitorPriceSnapshot.competitor_product_id
            == competitor_product.id
        )
        .order_by(CompetitorPriceSnapshot.observed_at.desc())
        .limit(1)
    )
    if previous is not None and request.observed_at <= previous.observed_at:
        raise MarketSnapshotConflictError(
            "observed_at must be later than the latest competitor snapshot: "
            f"{previous.observed_at.isoformat()}"
        )

    snapshot = CompetitorPriceSnapshot(
        id=uuid4(),
        competitor_product_id=competitor_product.id,
        price=request.price,
        currency=product.currency,
        promotion=request.promotion,
        observed_at=request.observed_at,
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)

    previous_price = previous.price if previous is not None else None
    change_amount = (
        snapshot.price - previous_price
        if previous_price is not None
        else Decimal("0.00")
    )
    change_percent = (
        calculate_price_change(previous_price, snapshot.price)
        if previous_price is not None
        else Decimal("0.00")
    )
    return MarketSnapshotResult(
        product_sku=product.sku,
        competitor_product_id=competitor_product.id,
        competitor_sku=competitor_product.competitor_sku,
        competitor_name=competitor_product.competitor.name,
        competitor_product_name=competitor_product.name,
        current_snapshot_id=snapshot.id,
        previous_snapshot_id=previous.id if previous is not None else None,
        previous_price=previous_price,
        current_price=snapshot.price,
        currency=snapshot.currency,
        change_type=classify_price_change(previous_price, snapshot.price),
        change_amount=change_amount,
        change_percent=change_percent,
        promotion=snapshot.promotion,
        observed_at=snapshot.observed_at,
        price_difference_from_ours=snapshot.price - product.price,
        is_cheaper_than_ours=snapshot.price < product.price,
    )
