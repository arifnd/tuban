import logging

from httpx2 import AsyncClient

from src.logging_filters import RedactSensitiveQueryFilter
from tests.tickets.helpers import login, make_user


async def test_security_headers(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.headers["x-frame-options"] == "DENY"
    assert resp.headers["x-content-type-options"] == "nosniff"
    assert resp.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "content-security-policy" in resp.headers


async def test_session_cookie_flags(client: AsyncClient) -> None:
    resp = await client.post("/auth/dev-login", json={"email": "cookie@example.com"})
    assert resp.status_code == 303
    set_cookie = resp.headers.get("set-cookie", "").lower()
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie
    assert "path=/" in set_cookie


async def test_csrf_required_for_post(client: AsyncClient, db) -> None:
    await make_user(db, "u@example.com")
    await login(client, "u@example.com")
    resp = await client.post("/profile", data={"name": "no token"})
    assert resp.status_code == 403


def test_redact_sensitive_query_filter() -> None:
    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, "GET /auth/callback?code=abc123&state=xyz789 HTTP/1.1", None, None)
    RedactSensitiveQueryFilter().filter(record)
    message = record.getMessage()
    assert "abc123" not in message
    assert "xyz789" not in message
    assert "[REDACTED]" in message


def test_production_requires_strong_secret(monkeypatch) -> None:
    from src import config as config_module
    from src.auth.config import AuthConfig

    monkeypatch.setattr(config_module.settings, "ENVIRONMENT", "production")
    try:
        AuthConfig(SESSION_SECRET="change-me-in-production")
    except RuntimeError:
        return
    raise AssertionError("AuthConfig should reject a weak secret in production")


def test_production_disables_dev_login(monkeypatch) -> None:
    from src import config as config_module
    from src.auth.config import AuthConfig

    monkeypatch.setattr(config_module.settings, "ENVIRONMENT", "production")
    try:
        AuthConfig(SESSION_SECRET="a-strong-secret-that-is-long-enough", DEV_LOGIN_ENABLED=True)
    except RuntimeError:
        return
    raise AssertionError("AuthConfig should reject dev login in production")
