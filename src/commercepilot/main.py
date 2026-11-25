from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

from commercepilot.api.router import router
from commercepilot.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="CommercePilot API",
    version="0.1.0",
    description="API and agent orchestration service for CommercePilot.",
)
app.include_router(router)


@app.middleware("http")
async def enforce_demo_read_only(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    if get_settings().read_only_demo and request.method not in {
        "GET",
        "HEAD",
        "OPTIONS",
    }:
        return JSONResponse(
            status_code=403,
            content={"detail": "This public demo is read-only."},
        )
    return await call_next(request)

