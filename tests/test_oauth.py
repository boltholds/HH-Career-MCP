"""Tests for the local HH.ru OAuth subsystem."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from pydantic import SecretStr

from hh_career_mcp.config import Settings
from hh_career_mcp.models import OAuthTokenSet
from hh_career_mcp.oauth import HHOAuthClient, OAuthTokenManager, OAuthTokenStore


def oauth_settings(tmp_path: Path) -> Settings:
    return Settings(
        _env_file=None,
        client_id="client-id",
        client_secret=SecretStr("client-secret"),
        redirect_uri="http://127.0.0.1:8766/oauth/callback",
        token_file=tmp_path / "token.json",
        user_agent="HH-Career-MCP-Test/0.2 (tests@example.com)",
    )


def test_authorization_request_contains_state_and_pkce(tmp_path: Path) -> None:
    settings = oauth_settings(tmp_path)
    oauth = HHOAuthClient(settings)
    request = oauth.create_authorization_request()
    query = parse_qs(urlparse(request.url).query)

    assert query["response_type"] == ["code"]
    assert query["client_id"] == ["client-id"]
    assert query["state"] == [request.state]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"][0]
    assert request.code_verifier


@pytest.mark.asyncio
async def test_expired_token_is_refreshed_and_rotated(tmp_path: Path) -> None:
    settings = oauth_settings(tmp_path)
    store = OAuthTokenStore(settings.token_file)
    store.save(
        OAuthTokenSet(
            access_token="expired-access",
            refresh_token="one-time-refresh",
            obtained_at=datetime.now(UTC) - timedelta(hours=2),
            expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
    )

    async with httpx.AsyncClient() as transport:
        oauth = HHOAuthClient(settings, transport)
        manager = OAuthTokenManager(settings, store=store, oauth_client=oauth)
        with respx.mock as router:
            route = router.post("https://api.hh.ru/token").mock(
                return_value=httpx.Response(
                    200,
                    json={
                        "access_token": "new-access",
                        "refresh_token": "new-refresh",
                        "token_type": "bearer",
                        "expires_in": 1209600,
                    },
                )
            )
            access_token = await manager.get_access_token()

    assert route.called
    assert access_token == "new-access"
    persisted = store.load()
    assert persisted is not None
    assert persisted.access_token == "new-access"
    assert persisted.refresh_token == "new-refresh"


def test_token_status_never_contains_secret_values(tmp_path: Path) -> None:
    settings = oauth_settings(tmp_path)
    store = OAuthTokenStore(settings.token_file)
    store.save(
        OAuthTokenSet(
            access_token="private-access",
            refresh_token="private-refresh",
            obtained_at=datetime.now(UTC),
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        )
    )
    manager = OAuthTokenManager(settings, store=store)

    status = manager.status()
    serialized = str(status)

    assert status["configured"] is True
    assert "private-access" not in serialized
    assert "private-refresh" not in serialized
