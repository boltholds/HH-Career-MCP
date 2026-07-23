"""MCP entry point and read-only HH.ru tools."""

from typing import Any

from mcp.server.fastmcp import FastMCP

from hh_career_mcp.config import get_settings
from hh_career_mcp.hh_client import HHAPIError, HHClient
from hh_career_mcp.models import VacancySearchParams

settings = get_settings()
hh = HHClient(settings)

mcp = FastMCP(
    "HH Career MCP",
    instructions=(
        "Use these tools to inspect HH.ru vacancies, the authenticated account, and its "
        "resumes. This version is read-only: do not claim that applications, messages, "
        "or resume changes were sent. Never expose OAuth credentials or raw token files."
    ),
    json_response=True,
    stateless_http=True,
    host=settings.mcp_host,
    port=settings.mcp_port,
    streamable_http_path=settings.mcp_path,
)


def _error_payload(error: Exception) -> dict[str, Any]:
    if isinstance(error, HHAPIError):
        return {
            "ok": False,
            "error": "hh_api_error",
            "status_code": error.status_code,
            "message": str(error),
            "details": error.payload,
        }
    return {"ok": False, "error": type(error).__name__, "message": str(error)}


@mcp.tool()
async def hh_connection_status() -> dict[str, Any]:
    """Check HH API reachability and sanitized OAuth state."""

    try:
        return {"ok": True, **await hh.health()}
    except Exception as error:  # MCP boundary: return structured errors to the caller.
        return _error_payload(error)


@mcp.tool()
async def hh_get_current_user() -> dict[str, Any]:
    """Return the OAuth-authenticated HH.ru user."""

    try:
        return {"ok": True, "user": await hh.get_current_user()}
    except Exception as error:
        return _error_payload(error)


@mcp.tool()
async def hh_search_vacancies(
    text: str | None = None,
    area: str | None = None,
    experience: str | None = None,
    employment: str | None = None,
    schedule: str | None = None,
    salary: int | None = None,
    currency: str | None = None,
    only_with_salary: bool = False,
    order_by: str = "publication_time",
    page: int = 0,
    per_page: int = 20,
) -> dict[str, Any]:
    """Search public HH.ru vacancies using a supported, typed subset of filters."""

    try:
        params = VacancySearchParams(
            text=text,
            area=area,
            experience=experience,
            employment=employment,
            schedule=schedule,
            salary=salary,
            currency=currency,
            only_with_salary=only_with_salary,
            order_by=order_by,
            page=page,
            per_page=per_page,
        )
        result = await hh.search_vacancies(params)
        return {"ok": True, **result.model_dump(mode="json")}
    except Exception as error:
        return _error_payload(error)


@mcp.tool()
async def hh_get_vacancy(vacancy_id: str) -> dict[str, Any]:
    """Return the full public vacancy card by HH.ru vacancy ID."""

    try:
        return {"ok": True, "vacancy": await hh.get_vacancy(vacancy_id)}
    except Exception as error:
        return _error_payload(error)


@mcp.tool()
async def hh_list_my_resumes() -> dict[str, Any]:
    """Return all resumes owned by the authenticated HH.ru applicant."""

    try:
        return {"ok": True, "resumes": await hh.list_my_resumes()}
    except Exception as error:
        return _error_payload(error)


@mcp.tool()
async def hh_get_my_resume(resume_id: str) -> dict[str, Any]:
    """Return one full resume available to the authenticated applicant."""

    try:
        return {"ok": True, "resume": await hh.get_my_resume(resume_id)}
    except Exception as error:
        return _error_payload(error)


def main() -> None:
    """Run the MCP server using the configured transport."""

    mcp.run(transport=settings.mcp_transport)


if __name__ == "__main__":
    main()
