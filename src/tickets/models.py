import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base, TimestampMixin, UUIDPrimaryKeyMixin, enum_col

if TYPE_CHECKING:
    from src.users.models import User


class TicketStatus(StrEnum):
    OPEN = "open"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketPriority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class TicketSource(StrEnum):
    WEB = "web"
    EMAIL = "email"


class TicketCategory(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ticket_categories"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    position: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    tickets: Mapped[list["Ticket"]] = relationship(back_populates="category")


class Ticket(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "tickets"
    __table_args__ = (
        Index("tickets_status_updated_idx", "status", "updated_at"),
        Index("tickets_assignee_status_idx", "assignee_id", "status"),
    )

    ticket_number: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    requester_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False)
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), index=True, nullable=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("ticket_categories.id"), index=True, nullable=True)
    status: Mapped[TicketStatus] = mapped_column(enum_col(TicketStatus, "ticket_status"), default=TicketStatus.OPEN, nullable=False)
    priority: Mapped[TicketPriority] = mapped_column(enum_col(TicketPriority, "ticket_priority"), default=TicketPriority.NORMAL, nullable=False)
    source: Mapped[TicketSource] = mapped_column(enum_col(TicketSource, "ticket_source"), default=TicketSource.WEB, nullable=False)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    category: Mapped["TicketCategory | None"] = relationship(back_populates="tickets", lazy="selectin")
    requester: Mapped["User"] = relationship(foreign_keys=[requester_id], lazy="selectin")
    assignee: Mapped["User | None"] = relationship(foreign_keys=[assignee_id], lazy="selectin")
    comments: Mapped[list["TicketComment"]] = relationship(back_populates="ticket", cascade="all, delete-orphan", lazy="selectin")
    attachments: Mapped[list["TicketAttachment"]] = relationship(back_populates="ticket", cascade="all, delete-orphan", lazy="selectin")


class TicketComment(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    __tablename__ = "ticket_comments"

    ticket_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tickets.id"), index=True, nullable=False)
    author_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), index=True, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    ticket: Mapped["Ticket"] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship(foreign_keys=[author_id], lazy="selectin")


class TicketAttachment(Base, UUIDPrimaryKeyMixin):
    __tablename__ = "ticket_attachments"

    ticket_id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("tickets.id"), index=True, nullable=False)
    comment_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("ticket_comments.id"), index=True, nullable=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    ticket: Mapped["Ticket"] = relationship(back_populates="attachments")
    uploader: Mapped["User"] = relationship(foreign_keys=[uploaded_by], lazy="selectin")


class TicketNumberSeq(Base):
    """Single-row counter backing collision-free ticket numbers."""

    __tablename__ = "ticket_number_seq"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
