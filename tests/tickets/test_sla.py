from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from httpx2 import AsyncClient

from src.tickets.models import Ticket, TicketPriority, TicketStatus
from src.tickets.service import sla_state
from src.tickets.utils import business_hours_add
from src.users.models import UserRole
from tests.tickets.helpers import csrf, login, make_ticket, make_user


def test_business_hours_add_within_day() -> None:
    monday = datetime(2026, 1, 5, 9, 0, tzinfo=UTC)
    assert business_hours_add(monday, 4) == datetime(2026, 1, 5, 13, 0, tzinfo=UTC)


def test_business_hours_add_rolls_over_weekend() -> None:
    friday = datetime(2026, 1, 9, 16, 0, tzinfo=UTC)
    assert business_hours_add(friday, 4) == datetime(2026, 1, 12, 12, 0, tzinfo=UTC)


def test_business_hours_add_skips_weekend_start() -> None:
    saturday = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
    assert business_hours_add(saturday, 2) == datetime(2026, 1, 12, 11, 0, tzinfo=UTC)


def test_sla_state_boundaries() -> None:
    now = datetime.now(UTC)
    assert sla_state(SimpleNamespace(status=TicketStatus.OPEN, sla_due_at=now - timedelta(hours=1))) == "breached"
    assert sla_state(SimpleNamespace(status=TicketStatus.OPEN, sla_due_at=now + timedelta(hours=1))) == "due_soon"
    assert sla_state(SimpleNamespace(status=TicketStatus.OPEN, sla_due_at=now + timedelta(days=3))) == "ok"
    assert sla_state(SimpleNamespace(status=TicketStatus.CLOSED, sla_due_at=now - timedelta(days=1))) == "met"


async def test_priority_change_recomputes_sla(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    await make_user(db, "agent@example.com", UserRole.AGENT)
    ticket = await make_ticket(db, requester, priority=TicketPriority.LOW)
    ticket_id = ticket.id
    original = ticket.sla_due_at

    await login(client, "agent@example.com")
    resp = await client.post(f"/tickets/{ticket_id}/priority", data={"_csrf": csrf(client.cookies), "priority": "urgent"})
    assert resp.status_code == 303

    db.expire_all()
    ticket = await db.get(Ticket, ticket_id)
    assert ticket.priority == TicketPriority.URGENT
    assert ticket.sla_due_at != original
