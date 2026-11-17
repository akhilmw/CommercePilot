from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="COMMERCEPILOT_",
        extra="ignore",
    )

    environment: str = "local"
    database_url: str = (
        "postgresql+psycopg://commercepilot:commercepilot@localhost:5433/"
        "commercepilot"
    )
    mcp_base_url: str = "http://localhost:8081"
    openai_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()

