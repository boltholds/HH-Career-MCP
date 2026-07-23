"""Async adapter for the official HH.ru API."""

from collections.abc import Mapping
from typing import Any

import httpx

from hh_career_mcp.config import Settings
from hh_career_mcp.models import VacancySearchParams, VacancySearchResult
from hh_career_mcp.oauth import OAuthNotAuthorizedError, OAuthTokenManager


class HHAPIError(RuntimeError):
    """Raised when HH.ru returns a non-successful response."""

    def __init__(self, status_code: int, message: str, payload: Any = None) -> None:
        super().__init__(f"HH API error {status_code}: {message}")
        self.status_code = status_code
        self.payload = payload


class HHClient:
    """Small HTTP client that keeps HH-specific concerns out of MCP tools."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
        token_manager: OAuthTokenManager | None = None,
    ) -> None:
        self._settings = settings
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            base_url=str(settings.api_base_url).rstrip("/"),
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
        )
        self._tokens = token_manager or OAuthTokenManager(settings)
        self._owns_tokens = token_manager is None

    async def _headers(self, *, require_auth: bool) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "HH-User-Agent": self._settings.user_agent,
            "User-Agent": self._settings.user_agent,
        }
        if require_auth:
            try:
                token = await self._tokens.get_access_token()
            except OAuthNotAuthorizedError as error:
                raise HHAPIError(401, str(error)) from error
            headers["Authorization"] = f"Bearer {token}"
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
            headers=await self._headers(require_auth=require_auth),
        )
        try:
            payload: Any = response.json()
        except ValueError:
            payload = {"description": response.text}

        if response.is_error:
            if isinstance(payload, dict):
                description = payload.get("description")
                errors = payload.get("errors")
                message = str(description or errors or response.reason_phrase)
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
            "oauth": self._tokens.status(),
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

    async def list_my_resumes(self) -> dict[str, Any]:
        """Return resumes owned by the authenticated applicant."""

        return await self._get("/resumes/mine", require_auth=True)

    async def get_my_resume(self, resume_id: str) -> dict[str, Any]:
        """Return a full resume available to the authenticated applicant."""

        resume_id = resume_id.strip()
        if not resume_id:
            raise ValueError("resume_id must not be empty")
        return await self._get(f"/resumes/{resume_id}", require_auth=True)

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()
        if self._owns_tokens:
            await self._tokens.close()
