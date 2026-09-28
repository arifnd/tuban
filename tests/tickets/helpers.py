from src.tickets import service as ticket_service
from src.tickets.models import Ticket, TicketPriority
from src.users.models import User
from tests.helpers import csrf, login, make_user  # noqa: F401  (re-exported for tests)

__all__ = ["csrf", "login", "make_ticket", "make_user"]


async def make_ticket(db, requester: User, *, subject: str = "Test ticket", priority: TicketPriority = TicketPriority.NORMAL, **fields) -> Ticket:
    ticket = await ticket_service.create_ticket(db, requester, subject=subject, description=fields.pop("description", "Body"), priority=priority)
    if fields:
        for key, value in fields.items():
            setattr(ticket, key, value)
    await db.commit()
    await db.refresh(ticket)
    return ticket
