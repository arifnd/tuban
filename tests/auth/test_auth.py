from httpx2 import AsyncClient

from src.auth import service as auth_service
from src.auth.exceptions import OAuthFailed
from src.auth.utils import decode_session_token


def _csrf(cookies) -> str:
    return decode_session_token(cookies["app_session"])["csrf"]


async def _dev_login(client: AsyncClient, email: str) -> None:
    client.cookies.clear()
    resp = await client.post("/auth/dev-login", json={"email": email})
    assert resp.status_code == 303


async def test_login_page_renders_dev_email_form(client: AsyncClient) -> None:
    resp = await client.get("/auth/login")
    assert resp.status_code == 200
    assert 'action="/auth/dev-login"' in resp.text
    assert 'type="email"' in resp.text


async def test_dev_login_redirects_to_dashboard(client: AsyncClient) -> None:
    resp = await client.post("/auth/dev-login", json={"email": "admin@example.com"})
    assert resp.status_code == 303
    assert "/dashboard" in resp.headers["location"]
    assert "app_session" in resp.cookies


async def test_dev_login_accepts_form_data(client: AsyncClient) -> None:
    resp = await client.post("/auth/dev-login", data={"email": "form@example.com"})
    assert resp.status_code == 303
    assert "app_session" in resp.cookies


async def test_dev_login_form_rejects_invalid_email(client: AsyncClient) -> None:
    resp = await client.post("/auth/dev-login", data={"email": "not-an-email"})
    assert resp.status_code == 303
    assert "auth/login" in resp.headers["location"]
    assert "error" in resp.headers["location"]


async def test_dev_login_json_rejects_invalid_email(client: AsyncClient) -> None:
    resp = await client.post("/auth/dev-login", json={"email": "not-an-email"})
    assert resp.status_code == 422


async def test_login_redirects_when_already_logged_in(client: AsyncClient) -> None:
    await _dev_login(client, "admin@example.com")
    resp = await client.get("/auth/login")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/dashboard"


async def test_google_oauth_init_sets_state_cookie(client: AsyncClient) -> None:
    resp = await client.get("/auth/login?google=1")
    assert resp.status_code == 303
    assert "accounts.google.com" in resp.headers["location"]
    assert "app_oauth_state" in resp.cookies


async def test_callback_missing_code_redirects_to_login(client: AsyncClient) -> None:
    resp = await client.get("/auth/callback")
    assert resp.status_code == 303
    assert "/auth/login?error=" in resp.headers["location"]


async def test_callback_oauth_failure_redirects_to_login(client: AsyncClient, monkeypatch) -> None:
    async def _boom(db, authorization_response, expected_state):
        raise OAuthFailed()

    monkeypatch.setattr(auth_service, "login_google", _boom)
    client.cookies.set("app_oauth_state", "state")
    resp = await client.get("/auth/callback?code=abc")
    assert resp.status_code == 303
    assert "/auth/login?error=" in resp.headers["location"]


async def test_callback_success_sets_session(client: AsyncClient, monkeypatch, db) -> None:
    user = await auth_service.dev_login(db, "admin@example.com")

    async def _fake(db, authorization_response, expected_state):
        return user

    monkeypatch.setattr(auth_service, "login_google", _fake)
    client.cookies.set("app_oauth_state", "state")
    resp = await client.get("/auth/callback?code=abc")
    assert resp.status_code == 303
    assert resp.headers["location"] == "/dashboard"
    assert "app_session" in resp.cookies
    assert "app_oauth_state" not in resp.cookies


async def test_logout_clears_session(client: AsyncClient) -> None:
    await _dev_login(client, "admin@example.com")
    assert "app_session" in client.cookies

    resp = await client.post("/auth/logout", data={"_csrf": _csrf(client.cookies)})
    assert resp.status_code == 303
    assert "app_session" not in client.cookies


async def test_middleware_rejects_missing_csrf(client: AsyncClient) -> None:
    await _dev_login(client, "admin@example.com")
    resp = await client.post("/auth/logout")
    assert resp.status_code == 403


async def test_middleware_rejects_multipart_without_csrf(client: AsyncClient) -> None:
    await _dev_login(client, "admin@example.com")
    resp = await client.post("/auth/logout", files={"file": ("dummy.txt", b"data", "text/plain")})
    assert resp.status_code == 403


async def test_dev_login_disabled_returns_404(client: AsyncClient, monkeypatch) -> None:
    from src.config import settings

    monkeypatch.setattr(settings, "ENVIRONMENT", "staging")
    resp = await client.post("/auth/dev-login", json={"email": "admin@example.com"})
    assert resp.status_code == 404


async def test_decode_session_token_returns_none_for_invalid_token() -> None:
    assert decode_session_token("not-a-token") is None


async def test_login_google_success_path(db, monkeypatch) -> None:
    class _FakeClient:
        async def fetch_token(self, **kwargs):
            return {"access_token": "tok"}

    monkeypatch.setattr("src.auth.utils.create_oauth_client", lambda token=None: _FakeClient())

    async def _profile(token):
        return {"sub": "g1", "email": "sso@example.com", "name": "SSO", "picture": "pic"}

    monkeypatch.setattr("src.auth.utils.fetch_google_profile", _profile)

    user = await auth_service.login_google(db, authorization_response="http://test/callback?code=abc", expected_state="state")
    assert user.email == "sso@example.com"
    assert user.google_id == "g1"


async def test_fetch_google_profile_rejects_unverified_email(monkeypatch) -> None:
    from jwt.exceptions import InvalidTokenError

    from src.auth.utils import fetch_google_profile

    class _FakeResponse:
        def raise_for_status(self) -> None:
            pass

        def json(self) -> dict:
            return {"email": "user@example.com"}

    class _FakeClient:
        async def get(self, url):
            return _FakeResponse()

    monkeypatch.setattr("src.auth.utils.create_oauth_client", lambda token=None: _FakeClient())

    try:
        await fetch_google_profile({})
    except InvalidTokenError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected InvalidTokenError")
