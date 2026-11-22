from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, cast
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from commercepilot.db.models import (
    ApprovalRequest,
    CompetitorProduct,
    OrchestrationRun,
    Product,
    Review,
)
from commercepilot.models.dashboard import LatestRunSummary, ProductPortfolioItem
from commercepilot.models.enums import ApprovalRequestStatus


class PortfolioProductNotFoundError(ValueError):
    pass


@dataclass(frozen=True)
class ProductCounts:
    reviews: int = 0
    competitors: int = 0
    pending_approvals: int = 0


def _count_by_product(
    session: Session,
    statement: Any,
) -> dict[UUID, int]:
    rows = cast(
        Iterable[tuple[UUID, int]],
        session.execute(statement).all(),
    )
    return {product_id: count for product_id, count in rows}


def list_product_portfolio(session: Session) -> list[ProductPortfolioItem]:
    products = list(session.scalars(select(Product).order_by(Product.name)))
    if not products:
        return []

    review_counts = _count_by_product(
        session,
        select(Review.product_id, func.count(Review.id)).group_by(Review.product_id),
    )
    competitor_counts = _count_by_product(
        session,
        select(
            CompetitorProduct.product_id,
            func.count(CompetitorProduct.id),
        ).group_by(CompetitorProduct.product_id),
    )
    approval_counts = _count_by_product(
        session,
        select(OrchestrationRun.product_id, func.count(ApprovalRequest.id))
        .join(ApprovalRequest, ApprovalRequest.run_id == OrchestrationRun.id)
        .where(ApprovalRequest.status == ApprovalRequestStatus.PENDING)
        .group_by(OrchestrationRun.product_id),
    )

    run_rank = (
        select(
            OrchestrationRun.id.label("run_id"),
            func.row_number()
            .over(
                partition_by=OrchestrationRun.product_id,
                order_by=OrchestrationRun.created_at.desc(),
            )
            .label("position"),
        )
        .subquery()
    )
    latest_runs = list(
        session.scalars(
            select(OrchestrationRun)
            .join(run_rank, run_rank.c.run_id == OrchestrationRun.id)
            .where(run_rank.c.position == 1)
        )
    )
    latest_by_product = {run.product_id: run for run in latest_runs}

    portfolio: list[ProductPortfolioItem] = []
    for product in products:
        latest = latest_by_product.get(product.id)
        portfolio.append(
            ProductPortfolioItem(
                id=product.id,
                sku=product.sku,
                name=product.name,
                category=product.category,
                price=product.price,
                currency=product.currency,
                status=product.status,
                catalog_version=product.catalog_version,
                review_count=review_counts.get(product.id, 0),
                competitor_count=competitor_counts.get(product.id, 0),
                pending_approval_count=approval_counts.get(product.id, 0),
                latest_run=(
                    LatestRunSummary.model_validate(latest)
                    if latest is not None
                    else None
                ),
                updated_at=product.updated_at,
            )
        )
    return portfolio


def list_product_runs(
    session: Session,
    product_sku: str,
    *,
    limit: int = 20,
) -> list[OrchestrationRun]:
    product = session.scalar(select(Product).where(Product.sku == product_sku))
    if product is None:
        raise PortfolioProductNotFoundError(f"Product not found: {product_sku}")

    return list(
        session.scalars(
            select(OrchestrationRun)
            .options(joinedload(OrchestrationRun.product))
            .where(OrchestrationRun.product_id == product.id)
            .order_by(OrchestrationRun.created_at.desc())
            .limit(limit)
        )
    )
