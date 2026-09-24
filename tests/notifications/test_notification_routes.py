from httpx2 import AsyncClient

from src.users.models import UserRole
from tests.tickets.helpers import csrf, login, make_ticket, make_user


async def test_notification_route_flow(client: AsyncClient, db) -> None:
    await make_user(db, "agent@example.com", UserRole.AGENT)
    requester = await make_user(db, "u@example.com")
    await make_ticket(db, requester)

    await login(client, "agent@example.com")
    assert (await client.get("/notifications/partial")).status_code == 200
    assert (await client.get("/notifications", params={"page": "1"})).status_code == 200

    data = (await client.get("/notifications/api")).json()
    notification_id = data["notifications"][0]["id"]

    assert (await client.get(f"/notifications/{notification_id}/open")).status_code == 303

    await make_ticket(db, requester, subject="Second")
    token = csrf(client.cookies)
    assert (await client.post("/notifications/read-many", json={"ids": [notification_id]}, headers={"X-CSRF-Token": token})).status_code == 303

    resp = await client.post(
        "/notifications/read-all",
        data={"_csrf": csrf(client.cookies)},
        headers={"HX-Request": "true", "HX-Target": "notif-dropdown"},
    )
    assert resp.status_code == 200
    assert "notif-dropdown" in resp.text

    resp = await client.post(f"/notifications/{notification_id}/read", data={"_csrf": csrf(client.cookies)})
    assert resp.status_code == 303


async def test_notifications_list_partial(client: AsyncClient, db) -> None:
    await make_user(db, "agent@example.com", UserRole.AGENT)
    requester = await make_user(db, "u@example.com")
    await make_ticket(db, requester)
    await login(client, "agent@example.com")

    resp = await client.post("/notifications/read-all", data={"_csrf": csrf(client.cookies)}, headers={"HX-Request": "true"})
    assert resp.status_code == 200
    assert "notifications-list" in resp.text
