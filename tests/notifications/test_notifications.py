from httpx2 import AsyncClient

from src.notifications import service as notification_service
from src.users.models import UserRole
from tests.tickets.helpers import csrf, login, make_ticket, make_user


async def test_new_ticket_notifies_agents(client: AsyncClient, db) -> None:
    agent = await make_user(db, "agent@example.com", UserRole.AGENT)
    await make_user(db, "u@example.com")

    await login(client, "u@example.com")
    resp = await client.post("/tickets", data={"_csrf": csrf(client.cookies), "subject": "Hello there"})
    assert resp.status_code == 303

    assert await notification_service.count_unread(db, agent.id) >= 1


async def test_internal_note_does_not_notify_requester(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    await make_user(db, "agent@example.com", UserRole.AGENT)
    ticket = await make_ticket(db, requester)

    await login(client, "agent@example.com")
    await client.post(f"/tickets/{ticket.id}/comments", data={"_csrf": csrf(client.cookies), "body": "private", "is_internal": "1"})

    assert await notification_service.count_unread(db, requester.id) == 0


async def test_mark_all_read(client: AsyncClient, db) -> None:
    agent = await make_user(db, "agent@example.com", UserRole.AGENT)
    requester = await make_user(db, "u@example.com")
    await make_ticket(db, requester)

    await login(client, "agent@example.com")
    assert (await client.get("/notifications")).status_code == 200
    assert (await client.get("/notifications/api")).status_code == 200

    resp = await client.post("/notifications/read-all", data={"_csrf": csrf(client.cookies)})
    assert resp.status_code == 303
    assert await notification_service.count_unread(db, agent.id) == 0
