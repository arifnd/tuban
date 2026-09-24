from httpx2 import AsyncClient
from sqlalchemy import select

from src.tickets.models import Ticket, TicketPriority, TicketStatus
from src.users.models import UserRole
from tests.tickets.helpers import csrf, login, make_ticket, make_user


async def _ticket(db, subject: str) -> Ticket:
    return (await db.execute(select(Ticket).where(Ticket.subject == subject))).scalar_one()


async def test_create_ticket_sets_defaults(client: AsyncClient, db) -> None:
    await make_user(db, "u@example.com")
    await login(client, "u@example.com")

    resp = await client.post("/tickets", data={"_csrf": csrf(client.cookies), "subject": "Cannot log in", "description": "help me", "priority": "high"})
    assert resp.status_code == 303

    ticket = await _ticket(db, "Cannot log in")
    assert ticket.status == TicketStatus.OPEN
    assert ticket.priority == TicketPriority.HIGH
    assert ticket.ticket_number.startswith("TKT-")
    assert ticket.sla_due_at is not None


async def test_invalid_priority_rejected(client: AsyncClient, db) -> None:
    await make_user(db, "u@example.com")
    await login(client, "u@example.com")
    resp = await client.post("/tickets", data={"_csrf": csrf(client.cookies), "subject": "Hi there", "priority": "bogus"})
    assert resp.status_code == 400


async def test_short_subject_rejected(client: AsyncClient, db) -> None:
    await make_user(db, "u@example.com")
    await login(client, "u@example.com")
    resp = await client.post("/tickets", data={"_csrf": csrf(client.cookies), "subject": "Hi"})
    assert resp.status_code == 400


async def test_list_scoping(client: AsyncClient, db) -> None:
    u1 = await make_user(db, "u1@example.com")
    u2 = await make_user(db, "u2@example.com")
    await make_ticket(db, u1, subject="Alpha ticket")
    await make_ticket(db, u2, subject="Beta ticket")

    await login(client, "u1@example.com")
    resp = await client.get("/tickets")
    assert "Alpha ticket" in resp.text
    assert "Beta ticket" not in resp.text

    await make_user(db, "agent@example.com", UserRole.AGENT)
    await login(client, "agent@example.com")
    resp = await client.get("/tickets")
    assert "Alpha ticket" in resp.text
    assert "Beta ticket" in resp.text


async def test_search_and_filters(client: AsyncClient, db) -> None:
    user = await make_user(db, "u@example.com")
    await make_ticket(db, user, subject="Printer broken", priority=TicketPriority.URGENT)
    await make_ticket(db, user, subject="VPN issue")

    await login(client, "u@example.com")
    resp = await client.get("/tickets", params={"q": "printer"})
    assert "Printer broken" in resp.text
    assert "VPN issue" not in resp.text

    resp = await client.get("/tickets", params={"priority": "urgent"})
    assert "Printer broken" in resp.text
    assert "VPN issue" not in resp.text

    resp = await client.get("/tickets/partials/list", headers={"HX-Request": "true"}, params={"q": "printer"})
    assert resp.status_code == 200
    assert "Printer broken" in resp.text
