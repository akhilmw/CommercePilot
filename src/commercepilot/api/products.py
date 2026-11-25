from datetime import UTC, datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from commercepilot.db.session import get_db
from commercepilot.models.dashboard import ProductPortfolioItem
from commercepilot.models.orchestration_api import OrchestrationRunRead
from commercepilot.models.review import (
    ReviewCreate,
    ReviewIngestionResult,
    SimulatedReviewCreate,
)
from commercepilot.services.product_portfolio import (
    PortfolioProductNotFoundError,
    list_product_portfolio,
    list_product_runs,
)
from commercepilot.services.review_ingestion import ingest_reviews

router = APIRouter(prefix="/api/products", tags=["products"])


@router.get("", response_model=list[ProductPortfolioItem])
def read_product_portfolio(
    session: Annotated[Session, Depends(get_db)],
) -> list[ProductPortfolioItem]:
    return list_product_portfolio(session)


@router.get("/{product_sku}/runs", response_model=list[OrchestrationRunRead])
def read_product_runs(
    product_sku: str,
    session: Annotated[Session, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[OrchestrationRunRead]:
    try:
        runs = list_product_runs(session, product_sku.upper(), limit=limit)
    except PortfolioProductNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    return [OrchestrationRunRead.model_validate(run) for run in runs]


@router.post(
    "/{product_sku}/reviews",
    response_model=ReviewIngestionResult,
    status_code=status.HTTP_201_CREATED,
)
def create_simulated_review(
    product_sku: str,
    request: SimulatedReviewCreate,
    session: Annotated[Session, Depends(get_db)],
) -> ReviewIngestionResult:
    review = ReviewCreate(
        source="review_simulator",
        source_review_id=str(uuid4()),
        rating=request.rating,
        title=request.title or None,
        body=request.body,
        reviewed_at=datetime.now(UTC),
    )
    try:
        result = ingest_reviews(session, product_sku.upper(), [review])
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(error)
        ) from error
    session.commit()
    return result
