import uuid

from pydantic import BaseModel, ConfigDict, Field

from src.tickets.models import TicketPriority, TicketSource, TicketStatus


class TicketCategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    position: int = 0


class TicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=255)
    description: str = ""
    category_id: uuid.UUID | None = None
    priority: TicketPriority = TicketPriority.NORMAL


class TicketFilter(BaseModel):
    q: str | None = None
    status: TicketStatus | None = None
    priority: TicketPriority | None = None
    category_id: uuid.UUID | None = None
    assignee_id: uuid.UUID | None = None
    requester_id: uuid.UUID | None = None
    sort: str = "updated"


class CommentCreate(BaseModel):
    body: str = Field(min_length=1)
    is_internal: bool = False


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ticket_number: str
    subject: str
    status: TicketStatus
    priority: TicketPriority
    source: TicketSource
