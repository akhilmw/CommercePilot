from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="COMMERCEPILOT_",
        extra="ignore",
    )

    environment: str = "local"
    read_only_demo: bool = False
    database_url: str = (
        "postgresql+psycopg://commercepilot:commercepilot@localhost:5432/commercepilot"
    )
    mcp_base_url: str = "http://localhost:8081"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"

    @property
    def checkpoint_database_url(self) -> str:
        return self.database_url.replace(
            "postgresql+psycopg://",
            "postgresql://",
            1,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
