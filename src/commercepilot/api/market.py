from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from commercepilot.db.session import get_db
from commercepilot.models.market import (
    MarketOverview,
    MarketSnapshotCreate,
    MarketSnapshotResult,
)
from commercepilot.services.market_api import (
    MarketCompetitorNotFoundError,
    MarketProductNotFoundError,
    MarketSnapshotConflictError,
    create_market_snapshot,
    get_market_overview,
)

router = APIRouter(prefix="/api/products", tags=["market simulator"])


@router.get("/{product_sku}/market", response_model=MarketOverview)
def read_market_overview(
    product_sku: str,
    session: Annotated[Session, Depends(get_db)],
) -> MarketOverview:
    try:
        return get_market_overview(session, product_sku.upper())
    except MarketProductNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error


@router.post(
    "/{product_sku}/market/snapshots",
    response_model=MarketSnapshotResult,
    status_code=status.HTTP_201_CREATED,
)
def create_snapshot(
    product_sku: str,
    request: MarketSnapshotCreate,
    session: Annotated[Session, Depends(get_db)],
) -> MarketSnapshotResult:
    try:
        return create_market_snapshot(
            session,
            product_sku.upper(),
            request,
        )
    except (MarketProductNotFoundError, MarketCompetitorNotFoundError) as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(error),
        ) from error
    except MarketSnapshotConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from error
