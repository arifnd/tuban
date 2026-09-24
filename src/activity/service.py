import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.activity.models import ActivityLog
from src.users.models import User


async def log(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    action: str,
    entity_type: str,
    entity_id: uuid.UUID | None = None,
    ticket_id: uuid.UUID | None = None,
    old_data: dict | None = None,
    new_data: dict | None = None,
) -> ActivityLog:
    entry = ActivityLog(
        ticket_id=ticket_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_data=old_data,
        new_data=new_data,
    )
    db.add(entry)
    await db.flush()
    return entry


async def count_activity_logs(db: AsyncSession) -> int:
    return (await db.scalar(select(func.count()).select_from(ActivityLog))) or 0


async def list_ticket_activity(db: AsyncSession, ticket_id: uuid.UUID, *, limit: int = 100) -> list[dict]:
    stmt = (
        select(ActivityLog, User.name.label("actor"))
        .join(User, User.id == ActivityLog.user_id)
        .where(ActivityLog.ticket_id == ticket_id)
        .order_by(ActivityLog.created_at.asc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [{"entry": entry, "actor": actor} for entry, actor in rows]


async def list_activity_logs(
    db: AsyncSession,
    *,
    user_id: uuid.UUID | None = None,
    entity_type: str | None = None,
    action: str | None = None,
    page: int = 1,
    per_page: int = 25,
) -> tuple[list[dict], int]:
    conditions = []
    if user_id is not None:
        conditions.append(ActivityLog.user_id == user_id)
    if entity_type:
        conditions.append(ActivityLog.entity_type == entity_type)
    if action:
        conditions.append(ActivityLog.action == action)
    total = (await db.scalar(select(func.count()).select_from(ActivityLog).where(*conditions))) or 0
    stmt = (
        select(ActivityLog, User.name.label("actor"), User.email.label("actor_email"))
        .join(User, User.id == ActivityLog.user_id, isouter=True)
        .where(*conditions)
        .order_by(ActivityLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    rows = (await db.execute(stmt)).all()
    return [{"entry": entry, "actor": actor, "actor_email": email} for entry, actor, email in rows], total


async def filter_users(db: AsyncSession) -> list[User]:
    return list((await db.execute(select(User).order_by(User.name))).scalars())


async def entity_types(db: AsyncSession) -> list[str]:
    rows = (await db.execute(select(ActivityLog.entity_type).distinct().order_by(ActivityLog.entity_type))).scalars().all()
    return list(rows)
