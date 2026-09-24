import statistics
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.activity.models import ActivityLog
from src.kb.models import KbArticle, KbArticleFeedback, KbArticleStatus, KbCategory
from src.templating import t
from src.tickets.models import Ticket, TicketStatus
from src.users.models import User, UserRole

ACTIVE_STATUSES = [TicketStatus.OPEN, TicketStatus.PENDING, TicketStatus.IN_PROGRESS]
RESOLVED_STATUSES = [TicketStatus.RESOLVED, TicketStatus.CLOSED]


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


async def ticket_volume(db: AsyncSession, start: date, end: date, group_by: str = "day") -> list[tuple[str, int]]:
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=UTC)
    end_dt = datetime.combine(end, datetime.max.time(), tzinfo=UTC)
    rows = (
        await db.execute(
            select(func.date(Ticket.created_at), func.count())
            .where(Ticket.created_at >= start_dt, Ticket.created_at <= end_dt)
            .group_by(func.date(Ticket.created_at))
        )
    ).all()
    buckets: dict[str, int] = {}
    for day, count in rows:
        day_str = str(day)
        if group_by == "month":
            key = day_str[:7]
        elif group_by == "week":
            parsed = datetime.strptime(day_str, "%Y-%m-%d").date()
            key = (parsed - timedelta(days=parsed.weekday())).isoformat()
        else:
            key = day_str
        buckets[key] = buckets.get(key, 0) + count
    return sorted(buckets.items())


async def _breakdown(db: AsyncSession, column, start: date, end: date) -> list[tuple[str, int]]:
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=UTC)
    end_dt = datetime.combine(end, datetime.max.time(), tzinfo=UTC)
    rows = (await db.execute(select(column, func.count()).where(Ticket.created_at >= start_dt, Ticket.created_at <= end_dt).group_by(column))).all()
    return [(value.value if hasattr(value, "value") else str(value), count) for value, count in rows]


async def status_breakdown(db: AsyncSession, start: date, end: date) -> list[tuple[str, int]]:
    return await _breakdown(db, Ticket.status, start, end)


async def priority_breakdown(db: AsyncSession, start: date, end: date) -> list[tuple[str, int]]:
    return await _breakdown(db, Ticket.priority, start, end)


async def sla_compliance(db: AsyncSession, start: date, end: date) -> dict:
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=UTC)
    end_dt = datetime.combine(end, datetime.max.time(), tzinfo=UTC)
    now = datetime.now(UTC)
    row = (
        await db.execute(
            select(
                func.count(Ticket.id).filter(Ticket.resolved_at.isnot(None), Ticket.sla_due_at.isnot(None), Ticket.resolved_at <= Ticket.sla_due_at),
                func.count(Ticket.id).filter(Ticket.resolved_at.isnot(None), Ticket.sla_due_at.isnot(None), Ticket.resolved_at > Ticket.sla_due_at),
                func.count(Ticket.id).filter(Ticket.status.in_(ACTIVE_STATUSES), Ticket.sla_due_at < now),
            ).where(Ticket.created_at >= start_dt, Ticket.created_at <= end_dt)
        )
    ).one()
    within, breached, overdue = row
    resolved = within + breached
    return {
        "within_sla": within,
        "breached": breached,
        "overdue_active": overdue,
        "total_resolved": resolved,
        "compliance": round(within / resolved * 100, 1) if resolved else 100.0,
    }


async def agent_workload(db: AsyncSession) -> list[tuple[str, int, int, int]]:
    rows = (
        await db.execute(
            select(
                User.name,
                func.count(Ticket.id).filter(Ticket.status.in_(ACTIVE_STATUSES)),
                func.count(Ticket.id),
                func.count(Ticket.id).filter(Ticket.status.in_(RESOLVED_STATUSES)),
            )
            .join(User, User.id == Ticket.assignee_id)
            .where(User.role.in_([UserRole.AGENT, UserRole.ADMIN]))
            .group_by(User.name)
            .order_by(func.count(Ticket.id).desc())
        )
    ).all()
    return [(name, open_count, total, resolved) for name, open_count, total, resolved in rows]


async def resolution_time(db: AsyncSession, start: date, end: date) -> dict:
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=UTC)
    end_dt = datetime.combine(end, datetime.max.time(), tzinfo=UTC)
    rows = (
        await db.execute(
            select(Ticket.created_at, Ticket.resolved_at).where(Ticket.resolved_at.isnot(None), Ticket.created_at >= start_dt, Ticket.created_at <= end_dt)
        )
    ).all()
    hours = [(_aware(resolved) - _aware(created)).total_seconds() / 3600 for created, resolved in rows if resolved and created]
    if not hours:
        return {"average": 0.0, "median": 0.0, "count": 0}
    return {"average": round(statistics.fmean(hours), 1), "median": round(statistics.median(hours), 1), "count": len(hours)}


async def kb_metrics(db: AsyncSession) -> dict:
    row = (
        await db.execute(
            select(
                func.count(KbArticle.id).filter(KbArticle.status == KbArticleStatus.PUBLISHED),
                func.coalesce(func.sum(KbArticle.view_count), 0),
            )
        )
    ).one()
    feedback = (
        await db.execute(
            select(
                func.count(KbArticleFeedback.id),
                func.count(KbArticleFeedback.id).filter(KbArticleFeedback.is_helpful.is_(True)),
            )
        )
    ).one()
    total_feedback, helpful = feedback
    top = (
        await db.execute(
            select(KbCategory.name, func.count(KbArticle.id))
            .join(KbArticle, KbArticle.category_id == KbCategory.id)
            .where(KbArticle.status == KbArticleStatus.PUBLISHED)
            .group_by(KbCategory.name)
            .order_by(func.count(KbArticle.id).desc())
            .limit(5)
        )
    ).all()
    return {
        "published": row[0],
        "views": int(row[1] or 0),
        "helpful_ratio": round(helpful / total_feedback * 100, 1) if total_feedback else 0.0,
        "top_categories": [(name, count) for name, count in top],
    }


async def activity_metrics(db: AsyncSession, start: date, end: date) -> int:
    start_dt = datetime.combine(start, datetime.min.time(), tzinfo=UTC)
    end_dt = datetime.combine(end, datetime.max.time(), tzinfo=UTC)
    return (await db.scalar(select(func.count()).select_from(ActivityLog).where(ActivityLog.created_at >= start_dt, ActivityLog.created_at <= end_dt))) or 0


REPORT_KEYS = ("ticket-volume", "status", "priority", "sla", "agents", "kb")


async def build_report(db: AsyncSession, report: str, start: date, end: date) -> tuple[str, list[str], list[list]]:
    if report == "ticket-volume":
        series = await ticket_volume(db, start, end)
        return t("reports.ticket_volume"), [t("reports.col_date"), t("reports.col_created")], [[label, str(count)] for label, count in series]
    if report == "status":
        rows = await status_breakdown(db, start, end)
        return t("reports.status"), [t("reports.col_status"), t("reports.col_count")], [[t("tickets.status_" + key), str(value)] for key, value in rows]
    if report == "priority":
        rows = await priority_breakdown(db, start, end)
        return t("reports.priority"), [t("reports.col_priority"), t("reports.col_count")], [[t("tickets.priority_" + key), str(value)] for key, value in rows]
    if report == "sla":
        metrics = await sla_compliance(db, start, end)
        return (
            t("reports.sla"),
            [t("reports.col_metric"), t("reports.col_value")],
            [
                [t("reports.within_sla"), str(metrics["within_sla"])],
                [t("reports.breached"), str(metrics["breached"])],
                [t("reports.overdue_active"), str(metrics["overdue_active"])],
                [t("reports.compliance"), str(metrics["compliance"])],
            ],
        )
    if report == "agents":
        rows = await agent_workload(db)
        return (
            t("reports.agents"),
            [t("reports.col_agent"), t("reports.col_open"), t("reports.col_total"), t("reports.col_resolved")],
            [[name, str(open_count), str(total), str(resolved)] for name, open_count, total, resolved in rows],
        )
    if report == "kb":
        metrics = await kb_metrics(db)
        return (
            t("reports.kb"),
            [t("reports.col_metric"), t("reports.col_value")],
            [
                [t("reports.published"), str(metrics["published"])],
                [t("reports.views"), str(metrics["views"])],
                [t("reports.helpful_ratio"), str(metrics["helpful_ratio"])],
                *[[f"{t('reports.category_prefix')}: {name}", str(count)] for name, count in metrics["top_categories"]],
            ],
        )
    raise ValueError(f"Unknown report: {report}")
