from fastapi import FastAPI

from commercepilot.api.router import router
from commercepilot.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="CommercePilot API",
    version="0.1.0",
    description="API and agent orchestration service for CommercePilot.",
)
app.include_router(router)

