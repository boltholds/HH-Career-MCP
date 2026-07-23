"""Tests for the official HH API adapter."""

import httpx
import pytest
import respx
from pydantic import SecretStr

from hh_career_mcp.config import Settings
from hh_career_mcp.hh_client import HHAPIError, HHClient
from hh_career_mcp.models import VacancySearchParams


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        access_token=SecretStr("test-token"),
        user_agent="HH-Career-MCP-Test/0.1 (tests@example.com)",
        api_base_url="https://api.hh.ru",
    )


@pytest.mark.asyncio
async def test_search_vacancies_normalizes_response(settings: Settings) -> None:
    response = {
        "items": [
            {
                "id": "123",
                "name": "Python Developer",
                "alternate_url": "https://hh.ru/vacancy/123",
                "employer": {"name": "Example"},
            }
        ],
        "found": 1,
        "page": 0,
        "pages": 1,
        "per_page": 20,
    }

    async with httpx.AsyncClient(base_url="https://api.hh.ru") as transport:
        client = HHClient(settings, transport)
        with respx.mock(base_url="https://api.hh.ru") as router:
            route = router.get("/vacancies").mock(return_value=httpx.Response(200, json=response))
            result = await client.search_vacancies(VacancySearchParams(text="Python"))

    assert route.called
    assert result.found == 1
    assert result.items[0].id == "123"
    assert result.items[0].name == "Python Developer"


@pytest.mark.asyncio
async def test_authenticated_method_requires_token() -> None:
    settings = Settings(
        _env_file=None,
        access_token=None,
        user_agent="HH-Career-MCP-Test/0.1 (tests@example.com)",
    )
    async with httpx.AsyncClient(base_url="https://api.hh.ru") as transport:
        client = HHClient(settings, transport)
        with pytest.raises(HHAPIError, match="HH_ACCESS_TOKEN"):
            await client.get_current_user()
