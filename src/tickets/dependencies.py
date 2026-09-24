import uuid
from typing import Annotated

from fastapi import Depends

from src.auth.dependencies import CurrentUser, DbDep
from src.tickets.exceptions import TicketForbidden, TicketNotFound
from src.tickets.models import Ticket
from src.users.dependencies import require_role
from src.users.models import User, UserRole

TicketEditor = Annotated[User, Depends(require_role("admin", "agent"))]
TicketAdmin = Annotated[User, Depends(require_role("admin"))]


async def get_ticket_by_id(db: DbDep, ticket_id: uuid.UUID) -> Ticket:
    ticket = await db.get(Ticket, ticket_id)
    if ticket is None:
        raise TicketNotFound()
    return ticket


TicketDep = Annotated[Ticket, Depends(get_ticket_by_id)]


def is_member(ticket: Ticket, user: User) -> bool:
    if user.role in (UserRole.ADMIN, UserRole.AGENT):
        return True
    return user.id in {ticket.requester_id, ticket.assignee_id}


async def require_member(ticket: TicketDep, user: CurrentUser) -> Ticket:
    if not is_member(ticket, user):
        raise TicketForbidden()
    return ticket


TicketMember = Annotated[Ticket, Depends(require_member)]
