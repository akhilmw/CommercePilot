from fastapi import APIRouter

from commercepilot.api.approvals import router as approvals_router
from commercepilot.api.market import router as market_router
from commercepilot.api.products import router as products_router
from commercepilot.api.runs import router as runs_router
from commercepilot.core.config import get_settings
from commercepilot.models.health import HealthResponse

router = APIRouter()
router.include_router(approvals_router)
router.include_router(market_router)
router.include_router(products_router)
router.include_router(runs_router)


@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(service="commercepilot-api")


@router.get("/api/capabilities", tags=["system"])
def read_capabilities() -> dict[str, bool]:
    return {"read_only_demo": get_settings().read_only_demo}
