import uuid
from datetime import UTC, datetime, timedelta

from fastapi import UploadFile
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.activity import service as activity_service
from src.kb import service as kb_service
from src.notifications import service as notification_service
from src.storage import service as storage_service
from src.tickets.constants import (
    DEFAULT_SLA_HOURS,
    EDITOR_ROLES,
    PRIORITY_ORDER,
    REQUESTER_TRANSITIONS,
    SLA_DUE_SOON_HOURS,
    STATUS_TRANSITIONS,
    TicketPriority,
    TicketStatus,
)
from src.tickets.dependencies import is_member
from src.tickets.exceptions import (
    CategoryHasTickets,
    CategoryNotFound,
    InvalidTransition,
    TicketForbidden,
    TicketNotFound,
)
from src.tickets.models import Ticket, TicketAttachment, TicketCategory, TicketComment
from src.tickets.utils import business_hours_add, next_ticket_number
from src.users import service as users_service
from src.users.models import User


def is_editor(user: User) -> bool:
    return user.role in EDITOR_ROLES


async def _notify(db: AsyncSession, recipients: list[User], *, type: str, title: str, body: str | None, link: str, actor_id: uuid.UUID) -> None:
    seen: set[uuid.UUID] = set()
    for recipient in recipients:
        if recipient is None or recipient.id == actor_id or recipient.id in seen:
            continue
        seen.add(recipient.id)
        await notification_service.create_notification(db, user_id=recipient.id, type=type, title=title, body=body, link=link)


# --------------------------------------------------------------------------- #
# Categories
# --------------------------------------------------------------------------- #
async def list_categories(db: AsyncSession) -> list[TicketCategory]:
    categories = list((await db.execute(select(TicketCategory).order_by(TicketCategory.position, TicketCategory.name))).scalars())
    rows = (await db.execute(select(Ticket.category_id, func.count(Ticket.id)).group_by(Ticket.category_id))).all()
    counts = {category_id: count for category_id, count in rows}
    for category in categories:
        category.ticket_count = counts.get(category.id, 0)
    return categories


async def get_category_by_id(db: AsyncSession, category_id: uuid.UUID) -> TicketCategory:
    category = await db.get(TicketCategory, category_id)
    if category is None:
        raise CategoryNotFound()
    return category


async def create_category(db: AsyncSession, actor: User, *, name: str, position: int = 0) -> TicketCategory:
    from src.kb.utils import slugify

    category = TicketCategory(name=name.strip(), slug=slugify(name), position=position)
    db.add(category)
    await db.flush()
    await activity_service.log(db, user_id=actor.id, action="create", entity_type="ticket_categories", entity_id=category.id, new_data={"name": category.name})
    await db.commit()
    await db.refresh(category)
    category.ticket_count = 0
    return category


async def update_category(db: AsyncSession, actor: User, category: TicketCategory, *, name: str, position: int) -> TicketCategory:
    from src.kb.utils import slugify

    old = {"name": category.name, "position": category.position}
    category.name = name.strip()
    category.slug = slugify(name)
    category.position = position
    await activity_service.log(
        db, user_id=actor.id, action="update", entity_type="ticket_categories", entity_id=category.id, old_data=old, new_data={"name": category.name}
    )
    await db.commit()
    await db.refresh(category)
    return category


async def delete_category(db: AsyncSession, actor: User, category: TicketCategory) -> None:
    count = (await db.scalar(select(func.count()).select_from(Ticket).where(Ticket.category_id == category.id))) or 0
    if count:
        raise CategoryHasTickets()
    await activity_service.log(db, user_id=actor.id, action="delete", entity_type="ticket_categories", entity_id=category.id, old_data={"name": category.name})
    await db.delete(category)
    await db.commit()


# --------------------------------------------------------------------------- #
# Tickets
# --------------------------------------------------------------------------- #
async def create_ticket(
    db: AsyncSession,
    requester: User,
    *,
    subject: str,
    description: str = "",
    category_id: uuid.UUID | None = None,
    priority: TicketPriority = TicketPriority.NORMAL,
) -> Ticket:
    now = datetime.now(UTC)
    ticket = Ticket(
        ticket_number=await next_ticket_number(db),
        subject=subject.strip(),
        description=description or "",
        requester_id=requester.id,
        category_id=category_id,
        priority=priority,
        status=TicketStatus.OPEN,
        sla_due_at=business_hours_add(now, DEFAULT_SLA_HOURS[priority]),
    )
    db.add(ticket)
    await db.flush()
    await activity_service.log(
        db,
        user_id=requester.id,
        action="create",
        entity_type="tickets",
        entity_id=ticket.id,
        ticket_id=ticket.id,
        new_data={"subject": ticket.subject, "priority": priority.value},
    )
    await _notify(
        db,
        await users_service.list_agents(db),
        type="ticket_created",
        title=f"New ticket: {ticket.subject}",
        body=ticket.ticket_number,
        link=f"/tickets/{ticket.id}",
        actor_id=requester.id,
    )
    await db.commit()
    await db.refresh(ticket)
    return ticket


async def get_ticket(db: AsyncSession, ticket_id: uuid.UUID) -> Ticket:
    ticket = await db.get(Ticket, ticket_id)
    if ticket is None:
        raise TicketNotFound()
    return ticket


async def list_tickets(
    db: AsyncSession,
    user: User,
    *,
    q: str | None = None,
    status: TicketStatus | None = None,
    priority: TicketPriority | None = None,
    category_id: uuid.UUID | None = None,
    assignee_id: uuid.UUID | None = None,
    requester_id: uuid.UUID | None = None,
    sort: str = "updated",
    page: int = 1,
    per_page: int = 25,
) -> tuple[list[Ticket], int]:
    stmt = select(Ticket)
    if not is_editor(user):
        stmt = stmt.where(or_(Ticket.requester_id == user.id, Ticket.assignee_id == user.id))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(or_(Ticket.subject.ilike(like), Ticket.description.ilike(like), Ticket.ticket_number.ilike(like)))
    if status is not None:
        stmt = stmt.where(Ticket.status == status)
    if priority is not None:
        stmt = stmt.where(Ticket.priority == priority)
    if category_id is not None:
        stmt = stmt.where(Ticket.category_id == category_id)
    if assignee_id is not None:
        stmt = stmt.where(Ticket.assignee_id == assignee_id)
    if requester_id is not None and is_editor(user):
        stmt = stmt.where(Ticket.requester_id == requester_id)

    if sort == "priority":
        order = [case(PRIORITY_ORDER, value=Ticket.priority).desc(), Ticket.updated_at.desc()]
    elif sort == "created":
        order = [Ticket.created_at.desc()]
    elif sort == "sla":
        order = [Ticket.sla_due_at.asc().nullslast(), Ticket.updated_at.desc()]
    else:
        order = [Ticket.updated_at.desc()]

    total = (await db.scalar(select(func.count()).select_from(stmt.subquery()))) or 0
    rows = (await db.execute(stmt.order_by(*order).offset((page - 1) * per_page).limit(per_page))).scalars().all()
    return list(rows), total


def can_transition(ticket: Ticket, target: TicketStatus, actor: User) -> bool:
    if target == ticket.status:
        return False
    if target not in STATUS_TRANSITIONS.get(ticket.status, set()):
        return False
    if is_editor(actor):
        return True
    return target in REQUESTER_TRANSITIONS.get(ticket.status, set())


def allowed_transitions(ticket: Ticket, actor: User) -> list[TicketStatus]:
    return [target for target in STATUS_TRANSITIONS.get(ticket.status, set()) if can_transition(ticket, target, actor)]


async def transition_status(db: AsyncSession, actor: User, ticket: Ticket, target: TicketStatus) -> Ticket:
    if not can_transition(ticket, target, actor):
        raise InvalidTransition(detail=f"Cannot move from {ticket.status.value} to {target.value}")
    old = ticket.status.value
    now = datetime.now(UTC)
    ticket.status = target
    if target == TicketStatus.RESOLVED:
        ticket.resolved_at = now
        ticket.closed_at = None
    elif target == TicketStatus.CLOSED:
        ticket.closed_at = now
        if ticket.resolved_at is None:
            ticket.resolved_at = now
    else:
        ticket.resolved_at = None
        ticket.closed_at = None
    await activity_service.log(
        db,
        user_id=actor.id,
        action="update",
        entity_type="tickets",
        entity_id=ticket.id,
        ticket_id=ticket.id,
        old_data={"status": old},
        new_data={"status": target.value},
    )
    if target in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
        await _notify(
            db,
            [ticket.requester],
            type="ticket_status",
            title=f"Ticket {ticket.ticket_number} {target.value}",
            body=ticket.subject,
            link=f"/tickets/{ticket.id}",
            actor_id=actor.id,
        )
    elif target == TicketStatus.OPEN and actor.id == ticket.requester_id and ticket.assignee:
        await _notify(
            db,
            [ticket.assignee],
            type="ticket_status",
            title=f"Ticket {ticket.ticket_number} reopened",
            body=ticket.subject,
            link=f"/tickets/{ticket.id}",
            actor_id=actor.id,
        )
    await db.commit()
    await db.refresh(ticket)
    return ticket


async def assign_ticket(db: AsyncSession, actor: User, ticket: Ticket, assignee: User | None) -> Ticket:
    if not is_editor(actor):
        raise TicketForbidden(detail="Only agents can assign tickets")
    old = str(ticket.assignee_id) if ticket.assignee_id else None
    ticket.assignee_id = assignee.id if assignee else None
    if assignee is not None and ticket.status == TicketStatus.OPEN:
        ticket.status = TicketStatus.IN_PROGRESS
    await activity_service.log(
        db,
        user_id=actor.id,
        action="update",
        entity_type="tickets",
        entity_id=ticket.id,
        ticket_id=ticket.id,
        old_data={"assignee_id": old},
        new_data={"assignee_id": str(assignee.id) if assignee else None},
    )
    if assignee is not None:
        await _notify(
            db,
            [assignee],
            type="ticket_assigned",
            title=f"Ticket {ticket.ticket_number} assigned to you",
            body=ticket.subject,
            link=f"/tickets/{ticket.id}",
            actor_id=actor.id,
        )
    await db.commit()
    await db.refresh(ticket)
    return ticket


async def claim_ticket(db: AsyncSession, actor: User, ticket: Ticket) -> Ticket:
    return await assign_ticket(db, actor, ticket, actor)


async def set_priority(db: AsyncSession, actor: User, ticket: Ticket, priority: TicketPriority) -> Ticket:
    old = ticket.priority.value
    ticket.priority = priority
    if ticket.status not in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
        ticket.sla_due_at = business_hours_add(datetime.now(UTC), DEFAULT_SLA_HOURS[priority])
    await activity_service.log(
        db,
        user_id=actor.id,
        action="update",
        entity_type="tickets",
        entity_id=ticket.id,
        ticket_id=ticket.id,
        old_data={"priority": old},
        new_data={"priority": priority.value},
    )
    await db.commit()
    await db.refresh(ticket)
    return ticket


def sla_state(ticket: Ticket) -> str:
    if ticket.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED) or ticket.sla_due_at is None:
        return "met"
    due = ticket.sla_due_at
    if due.tzinfo is None:
        due = due.replace(tzinfo=UTC)
    now = datetime.now(UTC)
    if due < now:
        return "breached"
    if due - now <= timedelta(hours=SLA_DUE_SOON_HOURS):
        return "due_soon"
    return "ok"


# --------------------------------------------------------------------------- #
# Comments & timeline
# --------------------------------------------------------------------------- #
async def list_comments(db: AsyncSession, ticket: Ticket, viewer: User) -> list[TicketComment]:
    stmt = select(TicketComment).where(TicketComment.ticket_id == ticket.id).order_by(TicketComment.created_at.asc())
    if not is_editor(viewer):
        stmt = stmt.where(TicketComment.is_internal.is_(False))
    return list((await db.execute(stmt)).scalars())


async def add_comment(db: AsyncSession, user: User, ticket: Ticket, body: str, is_internal: bool = False) -> TicketComment:
    if is_internal and not is_editor(user):
        is_internal = False
    comment = TicketComment(ticket_id=ticket.id, author_id=user.id, body=body, is_internal=is_internal)
    db.add(comment)
    await db.flush()
    if ticket.status == TicketStatus.PENDING and not is_internal and user.id == ticket.requester_id:
        ticket.status = TicketStatus.IN_PROGRESS if ticket.assignee_id else TicketStatus.OPEN
    await activity_service.log(
        db,
        user_id=user.id,
        action="comment",
        entity_type="ticket_comments",
        entity_id=comment.id,
        ticket_id=ticket.id,
        new_data={"is_internal": is_internal},
    )
    if is_internal:
        await _notify(
            db,
            [ticket.assignee],
            type="ticket_note",
            title=f"Internal note on {ticket.ticket_number}",
            body=ticket.subject,
            link=f"/tickets/{ticket.id}",
            actor_id=user.id,
        )
    else:
        recipients = [ticket.requester]
        if ticket.assignee is not None:
            recipients.append(ticket.assignee)
        await _notify(
            db,
            recipients,
            type="ticket_reply",
            title=f"New reply on {ticket.ticket_number}",
            body=ticket.subject,
            link=f"/tickets/{ticket.id}",
            actor_id=user.id,
        )
    await db.commit()
    await db.refresh(comment)
    return comment


async def delete_comment(db: AsyncSession, user: User, comment: TicketComment) -> None:
    if comment.author_id != user.id and not is_editor(user):
        raise TicketForbidden(detail="You cannot delete this comment")
    await db.delete(comment)
    await db.commit()


async def ticket_timeline(db: AsyncSession, ticket: Ticket, viewer: User) -> list[dict]:
    comments = await list_comments(db, ticket, viewer)
    activities = await activity_service.list_ticket_activity(db, ticket.id)
    events: list[dict] = [{"kind": "comment", "at": comment.created_at, "comment": comment} for comment in comments]
    events.extend({"kind": "activity", "at": row["entry"].created_at, "entry": row["entry"], "actor": row["actor"]} for row in activities)
    events.sort(key=lambda event: event["at"])
    return events


async def related_articles(db: AsyncSession, ticket: Ticket, viewer: User) -> list:
    words = [word.strip(".,:;!?").lower() for word in ticket.subject.split() if len(word.strip(".,:;!?")) > 3]
    if not words:
        return []
    results, _ = await kb_service.search_articles(db, viewer, " ".join(words[:3]), page=1, per_page=5)
    return results


# --------------------------------------------------------------------------- #
# Attachments
# --------------------------------------------------------------------------- #
async def add_attachment(db: AsyncSession, actor: User, ticket: Ticket, upload: UploadFile, *, comment_id: uuid.UUID | None = None) -> TicketAttachment:
    key, filename, size = await storage_service.save_upload(upload, prefix=f"tickets/{ticket.id}")
    attachment = TicketAttachment(
        ticket_id=ticket.id,
        comment_id=comment_id,
        file_name=filename,
        file_path=key,
        mime_type=upload.content_type,
        size_bytes=size,
        uploaded_by=actor.id,
    )
    db.add(attachment)
    await db.flush()
    await activity_service.log(
        db, user_id=actor.id, action="create", entity_type="ticket_attachments", entity_id=attachment.id, ticket_id=ticket.id, new_data={"file_name": filename}
    )
    await _notify(
        db,
        [ticket.requester, ticket.assignee],
        type="ticket_attachment",
        title=f"New attachment on {ticket.ticket_number}",
        body=filename,
        link=f"/tickets/{ticket.id}",
        actor_id=actor.id,
    )
    await db.commit()
    await db.refresh(attachment)
    return attachment


async def list_attachments(db: AsyncSession, ticket: Ticket) -> list[TicketAttachment]:
    stmt = select(TicketAttachment).where(TicketAttachment.ticket_id == ticket.id).order_by(TicketAttachment.created_at.asc())
    return list((await db.execute(stmt)).scalars())


async def get_attachment(db: AsyncSession, ticket: Ticket, attachment_id: uuid.UUID) -> TicketAttachment:
    attachment = (
        await db.execute(select(TicketAttachment).where(TicketAttachment.id == attachment_id, TicketAttachment.ticket_id == ticket.id))
    ).scalar_one_or_none()
    if attachment is None:
        raise TicketNotFound(detail="Attachment not found")
    return attachment


async def delete_attachment(db: AsyncSession, user: User, attachment: TicketAttachment) -> None:
    if attachment.uploaded_by != user.id and not is_editor(user):
        raise TicketForbidden(detail="You cannot delete this attachment")
    await storage_service.delete_upload(attachment.file_path)
    await db.delete(attachment)
    await db.commit()


def user_can_access_ticket(ticket: Ticket, user: User) -> bool:
    return is_member(ticket, user)


__all__ = [
    "add_attachment",
    "add_comment",
    "allowed_transitions",
    "assign_ticket",
    "can_transition",
    "claim_ticket",
    "create_category",
    "create_ticket",
    "delete_attachment",
    "delete_category",
    "delete_comment",
    "get_attachment",
    "get_category_by_id",
    "get_ticket",
    "is_editor",
    "list_attachments",
    "list_categories",
    "list_comments",
    "list_tickets",
    "related_articles",
    "set_priority",
    "sla_state",
    "ticket_timeline",
    "transition_status",
    "update_category",
    "user_can_access_ticket",
]
