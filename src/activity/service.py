import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.activity.models import ActivityLog


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
