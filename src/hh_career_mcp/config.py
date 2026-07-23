"""Application configuration."""

from functools import lru_cache
from pathlib import Path
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
    client_id: str | None = None
    client_secret: SecretStr | None = None
    redirect_uri: HttpUrl = HttpUrl("http://127.0.0.1:8766/oauth/callback")
    token_file: Path = Path(".data/hh/token.json")
    oauth_authorize_url: HttpUrl = HttpUrl("https://hh.ru/oauth/authorize")
    oauth_token_url: HttpUrl = HttpUrl("https://api.hh.ru/token")
    oauth_callback_bind_host: str = "127.0.0.1"
    oauth_callback_timeout_seconds: int = Field(default=180, ge=30, le=900)

    user_agent: str = Field(
        default="HH-Career-MCP/0.2 (configure-contact-email)",
        min_length=5,
    )
    api_base_url: HttpUrl = HttpUrl("https://api.hh.ru")
    request_timeout_seconds: float = Field(default=20.0, gt=0, le=120)

    mcp_transport: Literal["stdio", "streamable-http"] = "stdio"
    mcp_host: str = "127.0.0.1"
    mcp_port: int = Field(default=8000, ge=1, le=65535)
    mcp_path: str = Field(default="/mcp", pattern=r"^/")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached settings object."""

    return Settings()
