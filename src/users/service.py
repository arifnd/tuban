import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.exceptions import UserDeactivated
from src.config import settings
from src.users.exceptions import CannotDeactivateLastAdminError, UserNotFoundError
from src.users.models import User, UserRole

logger = logging.getLogger(__name__)


async def ensure_user(
    db: AsyncSession,
    *,
    google_id: str | None,
    email: str,
    name: str,
    avatar: str | None = None,
) -> User:
    """Registration policy: open self-registration via Google SSO. The single
    INITIAL_ADMIN_EMAIL account is granted admin on first login."""
    user = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
    if user is None:
        is_admin = bool(settings.INITIAL_ADMIN_EMAIL) and email.lower() == settings.INITIAL_ADMIN_EMAIL.lower()
        user = User(
            email=email,
            name=name,
            google_id=google_id,
            avatar=avatar,
            is_active=True,
            role=UserRole.ADMIN if is_admin else UserRole.USER,
        )
        try:
            async with db.begin_nested():
                db.add(user)
                await db.flush()
        except IntegrityError:
            user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        else:
            logger.info("created user %s email=%s role=%s", user.id, email, user.role.value)
    if not user.is_active:
        raise UserDeactivated()
    if google_id and not user.google_id:
        user.google_id = google_id
    if avatar:
        user.avatar = avatar
    user.last_login = datetime.now(UTC)
    await db.commit()
    await db.refresh(user)
    return user


async def list_users(
    db: AsyncSession,
    search: str | None = None,
    role: UserRole | None = None,
    is_active: bool | None = None,
    page: int = 1,
    per_page: int = 25,
    exclude_id: uuid.UUID | None = None,
) -> tuple[list[User], int]:
    stmt = select(User)
    if exclude_id is not None:
        stmt = stmt.where(User.id != exclude_id)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(or_(User.email.ilike(like), User.name.ilike(like)))
    if role is not None:
        stmt = stmt.where(User.role == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    total = (await db.scalar(select(func.count()).select_from(stmt.subquery()))) or 0
    rows = (await db.execute(stmt.order_by(User.created_at.desc()).offset((page - 1) * per_page).limit(per_page))).scalars().all()
    return list(rows), total


async def get_user_by_id(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise UserNotFoundError()
    return user


async def count_active_admins(db: AsyncSession, exclude_id: uuid.UUID | None = None) -> int:
    stmt = select(func.count()).select_from(User).where(User.role == UserRole.ADMIN, User.is_active.is_(True))
    if exclude_id is not None:
        stmt = stmt.where(User.id != exclude_id)
    return (await db.scalar(stmt)) or 0


async def ensure_not_last_active_admin(db: AsyncSession, user_id: uuid.UUID) -> None:
    if await count_active_admins(db, exclude_id=user_id) == 0:
        raise CannotDeactivateLastAdminError()


async def set_user_role(db: AsyncSession, user: User, role: UserRole) -> User:
    if user.role == UserRole.ADMIN and role != UserRole.ADMIN:
        await ensure_not_last_active_admin(db, user.id)
    user.role = role
    await db.commit()
    await db.refresh(user)
    return user


async def set_user_active(db: AsyncSession, user: User, is_active: bool) -> User:
    if not is_active and user.role == UserRole.ADMIN:
        await ensure_not_last_active_admin(db, user.id)
    user.is_active = is_active
    await db.commit()
    await db.refresh(user)
    return user


async def update_profile(db: AsyncSession, user: User, name: str) -> User:
    user.name = name
    await db.commit()
    await db.refresh(user)
    return user


async def list_agents(db: AsyncSession) -> list[User]:
    stmt = select(User).where(User.role.in_([UserRole.ADMIN, UserRole.AGENT]), User.is_active.is_(True)).order_by(User.name)
    return list((await db.execute(stmt)).scalars())
