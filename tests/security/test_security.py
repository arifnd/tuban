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


def test_local_requires_strong_secret(monkeypatch) -> None:
    from src import config as config_module
    from src.auth.config import AuthConfig

    monkeypatch.setattr(config_module.settings, "ENVIRONMENT", "local")
    for secret in ("", "change-me-in-production", "short", "a" * 40):
        try:
            AuthConfig(SESSION_SECRET=secret)
        except RuntimeError:
            continue
        raise AssertionError(f"AuthConfig should reject weak secret {secret!r} in local")


def test_test_environment_tolerates_weak_secret(monkeypatch) -> None:
    from src import config as config_module
    from src.auth.config import AuthConfig

    monkeypatch.setattr(config_module.settings, "ENVIRONMENT", "test")
    config = AuthConfig(SESSION_SECRET="change-me-in-production")
    assert config.SESSION_SECRET == "change-me-in-production"


def test_production_disables_dev_login(monkeypatch) -> None:
    from src import config as config_module
    from src.auth.config import AuthConfig

    monkeypatch.setattr(config_module.settings, "ENVIRONMENT", "production")
    try:
        AuthConfig(SESSION_SECRET="a-strong-secret-that-is-long-enough", DEV_LOGIN_ENABLED=True)
    except RuntimeError:
        return
    raise AssertionError("AuthConfig should reject dev login in production")


def test_dev_login_off_by_default(monkeypatch) -> None:
    from src import config as config_module
    from src.auth.config import AuthConfig

    monkeypatch.delenv("AUTH_DEV_LOGIN_ENABLED", raising=False)
    monkeypatch.setattr(config_module.settings, "ENVIRONMENT", "local")
    config = AuthConfig(SESSION_SECRET="a-strong-secret-that-is-long-enough")
    assert config.dev_login_enabled is False


def test_dev_login_enabled_locally_when_explicit(monkeypatch) -> None:
    from src import config as config_module
    from src.auth.config import AuthConfig

    monkeypatch.setattr(config_module.settings, "ENVIRONMENT", "local")
    config = AuthConfig(SESSION_SECRET="a-strong-secret-that-is-long-enough", DEV_LOGIN_ENABLED=True)
    assert config.dev_login_enabled is True


def test_secure_cookies_forced_outside_local(monkeypatch) -> None:
    from src import config as config_module
    from src.auth.config import AuthConfig

    monkeypatch.delenv("AUTH_DEV_LOGIN_ENABLED", raising=False)
    for env in ("staging", "production"):
        monkeypatch.setattr(config_module.settings, "ENVIRONMENT", env)
        config = AuthConfig(SESSION_SECRET="a-strong-secret-that-is-long-enough", SECURE_COOKIES=False)
        assert config.SECURE_COOKIES is True


async def test_body_size_limit_rejects_declared_oversize(client: AsyncClient, monkeypatch) -> None:
    from src.storage import service as storage_service

    monkeypatch.setattr(storage_service, "max_upload_size", lambda: 10)
    resp = await client.post("/auth/dev-login", data={"email": "a" * 70_000})
    assert resp.status_code == 413


async def test_body_size_limit_rejects_chunked_upload(client: AsyncClient, db, monkeypatch) -> None:
    from src.storage import service as storage_service

    await make_user(db, "u@example.com")
    await login(client, "u@example.com")
    monkeypatch.setattr(storage_service, "max_upload_size", lambda: 1024)

    async def _chunks():
        for _ in range(80):
            yield b"x" * 1024

    resp = await client.post(
        "/profile",
        content=_chunks(),
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 413
