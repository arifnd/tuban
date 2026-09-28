from src.settings import service as settings_service
from src.tickets.models import TicketPriority, TicketSource, TicketStatus
from src.users.models import UserRole

PAGE_SIZE = 10

EDITOR_ROLES = (UserRole.ADMIN, UserRole.AGENT)

# Legal status transitions, independent of who performs them.
STATUS_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.OPEN: {TicketStatus.IN_PROGRESS, TicketStatus.PENDING, TicketStatus.RESOLVED, TicketStatus.CLOSED},
    TicketStatus.IN_PROGRESS: {TicketStatus.PENDING, TicketStatus.RESOLVED, TicketStatus.CLOSED},
    TicketStatus.PENDING: {TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.CLOSED},
    TicketStatus.RESOLVED: {TicketStatus.CLOSED, TicketStatus.OPEN},
    TicketStatus.CLOSED: {TicketStatus.OPEN},
}

# Requesters may only confirm resolution (resolved -> closed) and reopen.
REQUESTER_TRANSITIONS: dict[TicketStatus, set[TicketStatus]] = {
    TicketStatus.RESOLVED: {TicketStatus.CLOSED, TicketStatus.OPEN},
    TicketStatus.CLOSED: {TicketStatus.OPEN},
}

# Sort weight so "urgent" ranks above "low".
PRIORITY_ORDER = {
    TicketPriority.LOW: 0,
    TicketPriority.NORMAL: 1,
    TicketPriority.HIGH: 2,
    TicketPriority.URGENT: 3,
}

DEFAULT_SLA_HOURS = {
    TicketPriority.URGENT: settings_service.DEFAULT_SLA_HOURS["sla_urgent_hours"],
    TicketPriority.HIGH: settings_service.DEFAULT_SLA_HOURS["sla_high_hours"],
    TicketPriority.NORMAL: settings_service.DEFAULT_SLA_HOURS["sla_normal_hours"],
    TicketPriority.LOW: settings_service.DEFAULT_SLA_HOURS["sla_low_hours"],
}

SLA_DUE_SOON_HOURS = 4

__all__ = [
    "DEFAULT_SLA_HOURS",
    "EDITOR_ROLES",
    "PAGE_SIZE",
    "PRIORITY_ORDER",
    "REQUESTER_TRANSITIONS",
    "SLA_DUE_SOON_HOURS",
    "STATUS_TRANSITIONS",
    "TicketPriority",
    "TicketSource",
    "TicketStatus",
]
