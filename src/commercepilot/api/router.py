from fastapi import APIRouter

from commercepilot.api.approvals import router as approvals_router
from commercepilot.api.market import router as market_router
from commercepilot.api.products import router as products_router
from commercepilot.api.runs import router as runs_router
from commercepilot.models.health import HealthResponse

router = APIRouter()
router.include_router(approvals_router)
router.include_router(market_router)
router.include_router(products_router)
router.include_router(runs_router)


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(service="commercepilot-api")
