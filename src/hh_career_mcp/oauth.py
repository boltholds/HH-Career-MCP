"""HH.ru OAuth2 authorization, refresh, and local token persistence."""

import asyncio
import base64
import hashlib
import json
import os
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

from hh_career_mcp.config import Settings
from hh_career_mcp.models import OAuthTokenSet


class OAuthConfigurationError(RuntimeError):
    """Raised when required HH OAuth application settings are missing."""


class OAuthNotAuthorizedError(RuntimeError):
    """Raised when no usable user access token is available."""


class OAuthTokenStoreError(RuntimeError):
    """Raised when the local token store cannot be read or written safely."""


@dataclass(frozen=True, slots=True)
class AuthorizationRequest:
    """Browser authorization URL and the secrets needed for callback validation."""

    url: str
    state: str
    code_verifier: str


class OAuthTokenStore:
    """Atomic JSON token store kept outside the repository."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> OAuthTokenSet | None:
        """Load a token pair, returning None when the store does not exist."""

        if not self.path.exists():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            return OAuthTokenSet.model_validate(payload)
        except (OSError, ValueError) as error:
            raise OAuthTokenStoreError(f"Unable to read OAuth token store: {error}") from error

    def save(self, token: OAuthTokenSet) -> None:
        """Persist a token pair using an atomic replace and restrictive permissions."""

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_name(f".{self.path.name}.{os.getpid()}.tmp")
            with temporary.open("w", encoding="utf-8", newline="\n") as handle:
                json.dump(token.model_dump(mode="json"), handle, ensure_ascii=False, indent=2)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.chmod(temporary, 0o600)
            except OSError:
                pass
            os.replace(temporary, self.path)
            try:
                os.chmod(self.path, 0o600)
            except OSError:
                pass
        except OSError as error:
            raise OAuthTokenStoreError(f"Unable to write OAuth token store: {error}") from error

    def clear(self) -> bool:
        """Delete the local token store if present."""

        try:
            self.path.unlink(missing_ok=False)
        except FileNotFoundError:
            return False
        except OSError as error:
            raise OAuthTokenStoreError(f"Unable to delete OAuth token store: {error}") from error
        return True


class HHOAuthClient:
    """Client for HH.ru authorization-code and refresh-token exchanges."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._owns_client = http_client is None
        self._client = http_client or httpx.AsyncClient(
            timeout=settings.request_timeout_seconds,
            follow_redirects=True,
        )

    def _credentials(self) -> tuple[str, str]:
        client_id = self._settings.client_id
        client_secret = self._settings.client_secret
        if not client_id or client_secret is None:
            raise OAuthConfigurationError(
                "HH_CLIENT_ID and HH_CLIENT_SECRET must be configured"
            )
        return client_id, client_secret.get_secret_value()

    def create_authorization_request(self) -> AuthorizationRequest:
        """Build an HH authorization URL with state and PKCE S256 protection."""

        client_id, _ = self._credentials()
        state = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        query = urlencode(
            {
                "response_type": "code",
                "client_id": client_id,
                "state": state,
                "redirect_uri": str(self._settings.redirect_uri),
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
        )
        return AuthorizationRequest(
            url=f"{str(self._settings.oauth_authorize_url)}?{query}",
            state=state,
            code_verifier=code_verifier,
        )

    async def exchange_code(self, code: str, code_verifier: str) -> OAuthTokenSet:
        """Exchange a short-lived authorization code for a user token pair."""

        client_id, client_secret = self._credentials()
        return await self._request_token(
            {
                "grant_type": "authorization_code",
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": str(self._settings.redirect_uri),
                "code": code,
                "code_verifier": code_verifier,
            }
        )

    async def refresh(self, refresh_token: str) -> OAuthTokenSet:
        """Exchange an expired token's one-time refresh token for a new pair."""

        client_id, client_secret = self._credentials()
        return await self._request_token(
            {
                "grant_type": "refresh_token",
                "client_id": client_id,
                "client_secret": client_secret,
                "refresh_token": refresh_token,
            }
        )

    async def _request_token(self, form: dict[str, str]) -> OAuthTokenSet:
        response = await self._client.post(
            str(self._settings.oauth_token_url),
            data=form,
            headers={
                "Accept": "application/json",
                "HH-User-Agent": self._settings.user_agent,
                "User-Agent": self._settings.user_agent,
            },
        )
        try:
            payload: Any = response.json()
        except ValueError:
            payload = {"description": response.text}
        if response.is_error:
            description = payload.get("description") if isinstance(payload, dict) else None
            raise OAuthNotAuthorizedError(
                f"HH OAuth token request failed with {response.status_code}: "
                f"{description or response.reason_phrase}"
            )
        if not isinstance(payload, dict):
            raise OAuthNotAuthorizedError("HH OAuth token response was not a JSON object")
        try:
            return OAuthTokenSet.from_response(payload)
        except (KeyError, TypeError, ValueError) as error:
            raise OAuthNotAuthorizedError(
                "HH OAuth token response did not contain a valid token pair"
            ) from error

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()


class OAuthTokenManager:
    """Resolve an access token from env or disk and refresh it after expiration."""

    def __init__(
        self,
        settings: Settings,
        *,
        store: OAuthTokenStore | None = None,
        oauth_client: HHOAuthClient | None = None,
    ) -> None:
        self._settings = settings
        self._store = store or OAuthTokenStore(settings.token_file)
        self._oauth = oauth_client
        self._owns_oauth = False
        self._refresh_lock = asyncio.Lock()

    def status(self) -> dict[str, Any]:
        """Return sanitized authorization state without exposing token values."""

        if self._settings.access_token is not None:
            return {
                "configured": True,
                "source": "environment",
                "expired": False,
                "refreshable": False,
                "expires_at": None,
            }
        token = self._store.load()
        if token is None:
            return {
                "configured": False,
                "source": None,
                "expired": None,
                "refreshable": False,
                "expires_at": None,
            }
        return {
            "configured": True,
            "source": "token_file",
            "expired": token.is_expired(),
            "refreshable": token.refresh_token is not None,
            "expires_at": token.expires_at.isoformat(),
        }

    async def get_access_token(self) -> str:
        """Return a usable token, refreshing a stored pair only after expiration."""

        environment_token = self._settings.access_token
        if environment_token is not None:
            return environment_token.get_secret_value()

        async with self._refresh_lock:
            token = self._store.load()
            if token is None:
                raise OAuthNotAuthorizedError(
                    "No HH OAuth token is available; run `hh-career-auth login`"
                )
            if not token.is_expired():
                return token.access_token
            if token.refresh_token is None:
                raise OAuthNotAuthorizedError(
                    "The HH access token expired and no refresh token is available"
                )
            if self._oauth is None:
                self._oauth = HHOAuthClient(self._settings)
                self._owns_oauth = True
            refreshed = await self._oauth.refresh(token.refresh_token)
            self._store.save(refreshed)
            return refreshed.access_token

    async def close(self) -> None:
        if self._owns_oauth and self._oauth is not None:
            await self._oauth.close()
