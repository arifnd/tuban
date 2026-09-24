from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.activity.models import ActivityLog
from src.dashboard.schemas import ChartSeries
from src.kb.models import KbArticle, KbArticleStatus
from src.tickets.models import Ticket, TicketStatus
from src.users.models import User, UserRole

ACTIVE_STATUSES = [TicketStatus.OPEN, TicketStatus.PENDING, TicketStatus.IN_PROGRESS]
CLOSED_STATUSES = [TicketStatus.RESOLVED, TicketStatus.CLOSED]


async def user_stats(db: AsyncSession, user: User) -> dict:
    row = (
        await db.execute(
            select(
                func.count(Ticket.id),
                func.count(Ticket.id).filter(Ticket.status.in_(ACTIVE_STATUSES)),
                func.count(Ticket.id).filter(Ticket.status.in_(CLOSED_STATUSES)),
            ).where(Ticket.requester_id == user.id)
        )
    ).one()
    return {"total": row[0], "open": row[1], "resolved": row[2]}


async def team_stats(db: AsyncSession) -> dict:
    now = datetime.now(UTC)
    row = (
        await db.execute(
            select(
                func.count(Ticket.id),
                func.count(Ticket.id).filter(Ticket.status == TicketStatus.OPEN),
                func.count(Ticket.id).filter(Ticket.status == TicketStatus.PENDING),
                func.count(Ticket.id).filter(Ticket.status == TicketStatus.IN_PROGRESS),
                func.count(Ticket.id).filter(Ticket.status == TicketStatus.RESOLVED),
                func.count(Ticket.id).filter(Ticket.status == TicketStatus.CLOSED),
                func.count(Ticket.id).filter(Ticket.assignee_id.is_(None), Ticket.status.in_(ACTIVE_STATUSES)),
                func.count(Ticket.id).filter(Ticket.sla_due_at < now, Ticket.status.in_(ACTIVE_STATUSES)),
            )
        )
    ).one()
    return {
        "total": row[0],
        "open": row[1],
        "pending": row[2],
        "in_progress": row[3],
        "resolved": row[4],
        "closed": row[5],
        "unassigned": row[6],
        "sla_breaches": row[7],
    }


async def kb_stats(db: AsyncSession) -> dict:
    row = (
        await db.execute(
            select(
                func.count(KbArticle.id).filter(KbArticle.status == KbArticleStatus.PUBLISHED),
                func.count(KbArticle.id).filter(KbArticle.status == KbArticleStatus.DRAFT),
                func.coalesce(func.sum(KbArticle.view_count), 0),
            )
        )
    ).one()
    return {"published": row[0], "drafts": row[1], "views": int(row[2] or 0)}


async def recent_tickets(db: AsyncSession, user: User, limit: int = 5) -> list[Ticket]:
    stmt = select(Ticket)
    if user.role == UserRole.USER:
        stmt = stmt.where(or_(Ticket.requester_id == user.id, Ticket.assignee_id == user.id))
    stmt = stmt.order_by(Ticket.updated_at.desc()).limit(limit)
    return list((await db.execute(stmt)).scalars())


async def recent_activity(db: AsyncSession, user: User, limit: int = 8) -> list[dict]:
    stmt = select(ActivityLog, User.name.label("actor")).join(User, User.id == ActivityLog.user_id)
    if user.role == UserRole.USER:
        stmt = stmt.where(ActivityLog.user_id == user.id)
    stmt = stmt.order_by(ActivityLog.created_at.desc()).limit(limit)
    rows = (await db.execute(stmt)).all()
    return [{"action": entry.action, "entity_type": entry.entity_type, "created_at": entry.created_at, "actor": actor} for entry, actor in rows]


async def ticket_trend(db: AsyncSession, days: int = 14) -> ChartSeries:
    today = datetime.now(UTC).date()
    start = datetime.combine(today - timedelta(days=days - 1), datetime.min.time(), tzinfo=UTC)
    created_rows = (
        await db.execute(select(func.date(Ticket.created_at), func.count()).where(Ticket.created_at >= start).group_by(func.date(Ticket.created_at)))
    ).all()
    resolved_rows = (
        await db.execute(select(func.date(Ticket.resolved_at), func.count()).where(Ticket.resolved_at >= start).group_by(func.date(Ticket.resolved_at)))
    ).all()
    created = {str(day): count for day, count in created_rows}
    resolved = {str(day): count for day, count in resolved_rows}
    labels: list[str] = []
    values: list[float] = []
    for offset in range(days):
        day = today - timedelta(days=days - 1 - offset)
        key = day.isoformat()
        labels.append(day.strftime("%b %d"))
        values.append(float(created.get(key, 0) + resolved.get(key, 0)))
    return ChartSeries(labels=labels, values=values)
