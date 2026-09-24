from httpx2 import AsyncClient

from src.auth.utils import decode_session_token


async def _login(client: AsyncClient, email: str) -> None:
    client.cookies.clear()
    resp = await client.post("/auth/dev-login", json={"email": email})
    assert resp.status_code == 303


async def test_dashboard_requires_authentication(client: AsyncClient) -> None:
    resp = await client.get("/dashboard", headers={"accept": "text/html"})
    assert resp.status_code == 303
    assert "/auth/login" in resp.headers["location"]

    resp = await client.get("/dashboard", headers={"accept": "application/json"})
    assert resp.status_code == 401


async def test_dashboard_renders_for_user(client: AsyncClient) -> None:
    await _login(client, "member@example.com")
    resp = await client.get("/dashboard")
    assert resp.status_code == 200
    assert "/tickets/new" in resp.text


async def test_dashboard_renders_for_staff(client: AsyncClient) -> None:
    await _login(client, "admin@example.com")
    resp = await client.get("/dashboard")
    assert resp.status_code == 200
    assert "Belum ditugaskan" in resp.text


async def test_stats_partial(client: AsyncClient) -> None:
    await _login(client, "admin@example.com")
    resp = await client.get("/dashboard/partials/stats")
    assert resp.status_code == 200


async def test_ticket_trend_endpoint(client: AsyncClient) -> None:
    await _login(client, "member@example.com")
    resp = await client.get("/dashboard/api/ticket-trend")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["labels"]) == 14
    assert len(body["values"]) == 14

    resp = await client.get("/dashboard/api/ticket-trend", params={"days": 7})
    assert len(resp.json()["labels"]) == 7

    resp = await client.get("/dashboard/api/ticket-trend", params={"days": 999})
    assert resp.status_code == 422


async def test_session_decodes(client: AsyncClient) -> None:
    await _login(client, "admin@example.com")
    assert decode_session_token(client.cookies["app_session"])["sub"]
