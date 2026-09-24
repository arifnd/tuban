from httpx2 import AsyncClient

from src.tickets.models import Ticket, TicketStatus
from src.users.models import UserRole
from tests.tickets.helpers import csrf, login, make_ticket, make_user


async def test_internal_notes_hidden_from_requester(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    await make_user(db, "agent@example.com", UserRole.AGENT)
    ticket = await make_ticket(db, requester)

    await login(client, "agent@example.com")
    resp = await client.post(f"/tickets/{ticket.id}/comments", data={"_csrf": csrf(client.cookies), "body": "secret note", "is_internal": "1"})
    assert resp.status_code == 303

    await login(client, "u@example.com")
    resp = await client.get(f"/tickets/{ticket.id}")
    assert "secret note" not in resp.text

    await login(client, "agent@example.com")
    resp = await client.get(f"/tickets/{ticket.id}")
    assert "secret note" in resp.text


async def test_requester_cannot_create_internal_note(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    ticket = await make_ticket(db, requester)

    await login(client, "u@example.com")
    await client.post(f"/tickets/{ticket.id}/comments", data={"_csrf": csrf(client.cookies), "body": "visible reply", "is_internal": "1"})
    resp = await client.get(f"/tickets/{ticket.id}")
    assert "visible reply" in resp.text


async def test_requester_reply_reopens_pending(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    ticket = await make_ticket(db, requester, status=TicketStatus.PENDING)
    ticket_id = ticket.id

    await login(client, "u@example.com")
    resp = await client.post(f"/tickets/{ticket_id}/comments", data={"_csrf": csrf(client.cookies), "body": "any update?"})
    assert resp.status_code == 303

    db.expire_all()
    ticket = await db.get(Ticket, ticket_id)
    assert ticket.status == TicketStatus.OPEN


async def test_non_member_forbidden(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    await make_user(db, "other@example.com")
    ticket = await make_ticket(db, requester)

    await login(client, "other@example.com")
    assert (await client.get(f"/tickets/{ticket.id}")).status_code == 403
