from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    anthropic_admin_api_key: str = Field(..., alias="ANTHROPIC_ADMIN_API_KEY")
    anthropic_org_id: str = Field(default="", alias="ANTHROPIC_ORG_ID")
    anthropic_api_base: str = Field(
        default="https://api.anthropic.com", alias="ANTHROPIC_API_BASE"
    )

    cache_db: str = Field(default="./benchy.sqlite", alias="BENCHY_CACHE_DB")

    host: str = Field(default="127.0.0.1", alias="BENCHY_HOST")
    port: int = Field(default=8000, alias="BENCHY_PORT")

    frontend_origin: str = Field(
        default="http://127.0.0.1:5173", alias="BENCHY_FRONTEND_ORIGIN"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
