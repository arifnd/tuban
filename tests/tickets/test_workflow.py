from httpx2 import AsyncClient

from src.tickets.models import Ticket, TicketStatus
from src.users.models import UserRole
from tests.tickets.helpers import csrf, login, make_ticket, make_user


async def test_agent_status_transitions(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    await make_user(db, "agent@example.com", UserRole.AGENT)
    ticket = await make_ticket(db, requester)
    ticket_id = ticket.id
    await login(client, "agent@example.com")

    resp = await client.post(f"/tickets/{ticket_id}/status", data={"_csrf": csrf(client.cookies), "status": "in_progress"})
    assert resp.status_code == 303
    db.expire_all()
    ticket = await db.get(Ticket, ticket_id)
    assert ticket.status == TicketStatus.IN_PROGRESS

    resp = await client.post(f"/tickets/{ticket_id}/status", data={"_csrf": csrf(client.cookies), "status": "resolved"})
    assert resp.status_code == 303
    db.expire_all()
    ticket = await db.get(Ticket, ticket_id)
    assert ticket.status == TicketStatus.RESOLVED
    assert ticket.resolved_at is not None

    resp = await client.post(f"/tickets/{ticket_id}/status", data={"_csrf": csrf(client.cookies), "status": "open"})
    assert resp.status_code == 303
    db.expire_all()
    ticket = await db.get(Ticket, ticket_id)
    assert ticket.status == TicketStatus.OPEN
    assert ticket.resolved_at is None


async def test_requester_cannot_close_open_ticket(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    ticket = await make_ticket(db, requester)
    await login(client, "u@example.com")
    resp = await client.post(f"/tickets/{ticket.id}/status", data={"_csrf": csrf(client.cookies), "status": "closed"})
    assert resp.status_code == 400


async def test_requester_can_close_resolved_ticket(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    ticket = await make_ticket(db, requester, status=TicketStatus.RESOLVED)
    ticket_id = ticket.id
    await login(client, "u@example.com")
    resp = await client.post(f"/tickets/{ticket_id}/close", data={"_csrf": csrf(client.cookies)})
    assert resp.status_code == 303
    db.expire_all()
    ticket = await db.get(Ticket, ticket_id)
    assert ticket.status == TicketStatus.CLOSED


async def test_assign_moves_open_ticket_to_in_progress(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    agent = await make_user(db, "agent@example.com", UserRole.AGENT)
    ticket = await make_ticket(db, requester)
    ticket_id = ticket.id
    await login(client, "agent@example.com")

    resp = await client.post(f"/tickets/{ticket_id}/assign", data={"_csrf": csrf(client.cookies), "assignee_id": str(agent.id)})
    assert resp.status_code == 303
    db.expire_all()
    ticket = await db.get(Ticket, ticket_id)
    assert ticket.assignee_id == agent.id
    assert ticket.status == TicketStatus.IN_PROGRESS


async def test_requester_cannot_assign(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    ticket = await make_ticket(db, requester)
    await login(client, "u@example.com")
    resp = await client.post(f"/tickets/{ticket.id}/assign", data={"_csrf": csrf(client.cookies), "assignee_id": str(requester.id)})
    assert resp.status_code == 403
