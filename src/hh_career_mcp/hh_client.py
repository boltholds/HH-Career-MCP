"""Async adapter for the official HH.ru API."""

from collections.abc import Mapping
from typing import Any

import httpx

from hh_career_mcp.config import Settings
from hh_career_mcp.models import VacancySearchParams, VacancySearchResult


class HHAPIError(RuntimeError):
    """Raised when HH.ru returns a non-successful response."""

    def __init__(self, status_code: int, message: str, payload: Any = None) -> None:
        super().__init__(f"HH API error {status_code}: {message}")
        self.status_code = status_code
        self.payload = payload


class HHClient:
    """Small HTTP client that keeps HH-specific concerns out of MCP tools."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=str(settings.api_base_url).rstrip("/"),
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
        )

    @property
    def auth_configured(self) -> bool:
        return self._settings.access_token is not None

    def _headers(self, *, require_auth: bool) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "HH-User-Agent": self._settings.user_agent,
            "User-Agent": self._settings.user_agent,
        }
        token = self._settings.access_token
        if token is not None:
            headers["Authorization"] = f"Bearer {token.get_secret_value()}"
        elif require_auth:
            raise HHAPIError(401, "HH_ACCESS_TOKEN is not configured")
        return headers

    async def _get(
        self,
        path: str,
        *,
        params: Mapping[str, str | int | bool] | None = None,
        require_auth: bool = False,
    ) -> dict[str, Any]:
        response = await self._client.get(
            path,
            params=params,
            headers=self._headers(require_auth=require_auth),
        )
        try:
            payload: Any = response.json()
        except ValueError:
            payload = {"description": response.text}

        if response.is_error:
            if isinstance(payload, dict):
                message = str(payload.get("description") or payload.get("errors") or response.reason_phrase)
            else:
                message = response.reason_phrase
            raise HHAPIError(response.status_code, message, payload)

        if not isinstance(payload, dict):
            raise HHAPIError(response.status_code, "Unexpected non-object response", payload)
        return payload

    async def health(self) -> dict[str, Any]:
        payload = await self._get("/dictionaries")
        return {
            "api_reachable": True,
            "auth_configured": self.auth_configured,
            "dictionaries_loaded": bool(payload),
        }

    async def get_current_user(self) -> dict[str, Any]:
        return await self._get("/me", require_auth=True)

    async def search_vacancies(self, params: VacancySearchParams) -> VacancySearchResult:
        payload = await self._get("/vacancies", params=params.to_query())
        return VacancySearchResult.model_validate(payload)

    async def get_vacancy(self, vacancy_id: str) -> dict[str, Any]:
        vacancy_id = vacancy_id.strip()
        if not vacancy_id:
            raise ValueError("vacancy_id must not be empty")
        return await self._get(f"/vacancies/{vacancy_id}")

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
