"""Application configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="HH_",
        extra="ignore",
    )

    access_token: SecretStr | None = None
    user_agent: str = Field(
        default="HH-Career-MCP/0.1 (configure-contact-email)",
        min_length=5,
    )
    api_base_url: HttpUrl = HttpUrl("https://api.hh.ru")
    request_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    mcp_transport: Literal["stdio", "streamable-http"] = "stdio"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings object."""

    return Settings()
