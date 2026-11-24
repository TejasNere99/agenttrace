from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Environment-backed settings. Secrets are read only from the environment/.env."""

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    mongodb_uri: str | None = Field(default=None, repr=False)
    mongodb_database: str = "agenttrace"
    app_env: str = "development"
    api_host: str = "127.0.0.1"
    api_port: int = Field(default=8000, ge=1, le=65535)
    frontend_url: str = "http://localhost:5173"

    @field_validator("mongodb_uri", mode="before")
    @classmethod
    def blank_uri_is_unconfigured(cls, value: object) -> object:
        return None if value == "" else value

    @property
    def cors_origins(self) -> list[str]:
        """Allow the configured frontend and loopback Vite host only."""
        origins = [item.strip().rstrip("/") for item in self.frontend_url.split(",")]
        return [origin for origin in origins if origin]


@lru_cache
def get_settings() -> Settings:
    return Settings()
