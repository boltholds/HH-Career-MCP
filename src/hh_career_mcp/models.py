"""Typed models exposed by the MCP tools."""

from typing import Any

from pydantic import BaseModel, Field


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
