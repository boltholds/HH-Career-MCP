"""Local browser-based OAuth helper for HH Career MCP."""

import argparse
import asyncio
import json
import secrets
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Empty, Queue
from typing import NamedTuple
from urllib.parse import parse_qs, urlparse

from hh_career_mcp.config import Settings, get_settings
from hh_career_mcp.oauth import HHOAuthClient, OAuthTokenManager, OAuthTokenStore


class CallbackResult(NamedTuple):
    code: str | None
    error: str | None


def _html_page(title: str, message: str) -> bytes:
    return (
        "<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
        f"<title>{title}</title></head><body><h1>{title}</h1><p>{message}</p>"
        "<p>Это окно можно закрыть.</p></body></html>"
    ).encode("utf-8")


async def _wait_for_callback(
    settings: Settings,
    *,
    expected_state: str,
    authorization_url: str,
) -> str:
    redirect = urlparse(str(settings.redirect_uri))
    if redirect.scheme != "http" or redirect.hostname not in {"127.0.0.1", "localhost"}:
        raise RuntimeError(
            "The built-in OAuth helper requires an http://127.0.0.1 or localhost redirect URI"
        )
    if redirect.query or redirect.fragment:
        raise RuntimeError("The built-in OAuth helper does not support query or fragment in redirect URI")

    callback_path = redirect.path or "/"
    callback_port = redirect.port or 80
    results: Queue[CallbackResult] = Queue(maxsize=1)

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler API.
            request = urlparse(self.path)
            if request.path != callback_path:
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            query = parse_qs(request.query)
            received_state = query.get("state", [""])[0]
            oauth_error = query.get("error", [""])[0]
            code = query.get("code", [""])[0]

            if not secrets.compare_digest(received_state, expected_state):
                result = CallbackResult(None, "OAuth state mismatch")
            elif oauth_error:
                result = CallbackResult(None, f"HH authorization failed: {oauth_error}")
            elif not code:
                result = CallbackResult(None, "HH authorization callback did not contain a code")
            else:
                result = CallbackResult(code, None)

            try:
                results.put_nowait(result)
            except Exception:
                pass

            success = result.error is None
            body = _html_page(
                "HH Career MCP",
                "Авторизация завершена успешно." if success else str(result.error),
            )
            self.send_response(HTTPStatus.OK if success else HTTPStatus.BAD_REQUEST)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(
        (settings.oauth_callback_bind_host, callback_port),
        CallbackHandler,
    )
    server.timeout = settings.oauth_callback_timeout_seconds
    try:
        opened = webbrowser.open(authorization_url, new=1, autoraise=True)
        if not opened:
            print("Откройте URL авторизации вручную:")
            print(authorization_url)
        await asyncio.to_thread(server.handle_request)
    finally:
        server.server_close()

    try:
        result = results.get_nowait()
    except Empty as error:
        raise TimeoutError(
            f"HH OAuth callback was not received within "
            f"{settings.oauth_callback_timeout_seconds} seconds"
        ) from error
    if result.error:
        raise RuntimeError(result.error)
    if result.code is None:
        raise RuntimeError("HH OAuth callback did not return an authorization code")
    return result.code


async def _login(settings: Settings) -> int:
    oauth = HHOAuthClient(settings)
    try:
        request = oauth.create_authorization_request()
        print("Открываю HH.ru для авторизации приложения...")
        code = await _wait_for_callback(
            settings,
            expected_state=request.state,
            authorization_url=request.url,
        )
        token = await oauth.exchange_code(code, request.code_verifier)
        OAuthTokenStore(settings.token_file).save(token)
        print(f"Токен сохранён: {settings.token_file}")
        print(f"Действует до: {token.expires_at.isoformat()}")
        return 0
    finally:
        await oauth.close()


async def _status(settings: Settings) -> int:
    manager = OAuthTokenManager(settings)
    try:
        print(json.dumps(manager.status(), ensure_ascii=False, indent=2))
        return 0
    finally:
        await manager.close()


def _clear(settings: Settings) -> int:
    deleted = OAuthTokenStore(settings.token_file).clear()
    print("Локальный OAuth-токен удалён." if deleted else "Локального OAuth-токена нет.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage local HH.ru OAuth authorization")
    parser.add_argument("command", choices=("login", "status", "clear"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    settings = get_settings()
    if args.command == "login":
        raise SystemExit(asyncio.run(_login(settings)))
    if args.command == "status":
        raise SystemExit(asyncio.run(_status(settings)))
    raise SystemExit(_clear(settings))


if __name__ == "__main__":
    main()
