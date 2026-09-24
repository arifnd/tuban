import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.notifications.models import Notification


async def create_notification(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    type: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
) -> Notification:
    notification = Notification(user_id=user_id, type=type, title=title, body=body, link=link)
    db.add(notification)
    await db.flush()
    return notification


async def count_unread(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user_id, Notification.is_read.is_(False)))
    return result or 0


async def count_notifications(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.scalar(select(func.count()).select_from(Notification).where(Notification.user_id == user_id))
    return result or 0


async def list_notifications(db: AsyncSession, user_id: uuid.UUID, *, limit: int = 50, unread_only: bool = False) -> list[Notification]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.is_read.is_(False))
    result = await db.execute(stmt.order_by(Notification.created_at.desc()).limit(limit))
    return list(result.scalars())


async def list_notifications_page(db: AsyncSession, user_id: uuid.UUID, *, offset: int = 0, limit: int = 25) -> list[Notification]:
    result = await db.execute(select(Notification).where(Notification.user_id == user_id).order_by(Notification.created_at.desc()).offset(offset).limit(limit))
    return list(result.scalars())


async def get_notification(db: AsyncSession, notification_id: uuid.UUID, user_id: uuid.UUID) -> Notification | None:
    return await db.scalar(select(Notification).where(Notification.id == notification_id, Notification.user_id == user_id))


async def mark_read(db: AsyncSession, notification_id: uuid.UUID, user_id: uuid.UUID) -> bool:
    notification = await get_notification(db, notification_id, user_id)
    if notification is None:
        return False
    notification.is_read = True
    notification.read_at = datetime.now(UTC)
    await db.commit()
    return True


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID) -> None:
    result = await db.execute(select(Notification).where(Notification.user_id == user_id, Notification.is_read.is_(False)))
    now = datetime.now(UTC)
    for notification in result.scalars():
        notification.is_read = True
        notification.read_at = now
    await db.commit()
