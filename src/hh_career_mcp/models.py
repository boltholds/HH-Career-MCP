"""Typed models exposed by the MCP tools and OAuth subsystem."""

from datetime import UTC, datetime, timedelta
from typing import Any

from pydantic import BaseModel, Field


class OAuthTokenSet(BaseModel):
    """Persisted HH.ru user OAuth token pair."""

    access_token: str = Field(min_length=1)
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_at: datetime
    obtained_at: datetime

    @classmethod
    def from_response(
        cls,
        payload: dict[str, Any],
        *,
        now: datetime | None = None,
    ) -> "OAuthTokenSet":
        """Create a token pair from the HH token endpoint response."""

        current = now or datetime.now(UTC)
        expires_in = int(payload["expires_in"])
        return cls(
            access_token=str(payload["access_token"]),
            refresh_token=(
                str(payload["refresh_token"]) if payload.get("refresh_token") else None
            ),
            token_type=str(payload.get("token_type", "bearer")),
            obtained_at=current,
            expires_at=current + timedelta(seconds=expires_in),
        )

    def is_expired(self, *, now: datetime | None = None) -> bool:
        """Return true only after the access token lifetime has elapsed."""

        current = now or datetime.now(UTC)
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        return current >= expires_at


class VacancySearchParams(BaseModel):
    """Supported subset of the HH vacancy search parameters."""

    text: str | None = Field(default=None, max_length=512)
    area: str | None = None
    experience: str | None = None
    employment: str | None = None
    schedule: str | None = None
    salary: int | None = Field(default=None, ge=0)
    currency: str | None = None
    only_with_salary: bool = False
    order_by: str = "publication_time"
    page: int = Field(default=0, ge=0)
    per_page: int = Field(default=20, ge=1, le=100)

    def to_query(self) -> dict[str, str | int | bool]:
        """Convert set fields to HH API query parameters."""

        return {
            key: value
            for key, value in self.model_dump(exclude_none=True).items()
            if value != ""
        }


class VacancySummary(BaseModel):
    """Stable subset of a vacancy search item."""

    id: str
    name: str
    alternate_url: str | None = None
    employer: dict[str, Any] | None = None
    area: dict[str, Any] | None = None
    salary: dict[str, Any] | None = None
    experience: dict[str, Any] | None = None
    employment: dict[str, Any] | None = None
    schedule: dict[str, Any] | None = None
    snippet: dict[str, Any] | None = None
    published_at: str | None = None


class VacancySearchResult(BaseModel):
    """Normalized vacancy search response."""

    items: list[VacancySummary]
    found: int
    page: int
    pages: int
    per_page: int
