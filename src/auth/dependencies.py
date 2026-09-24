import secrets
import uuid
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.constants import CSRF_FORM_FIELD, CSRF_HEADER, SESSION_COOKIE_NAME
from src.auth.exceptions import NotAuthenticated
from src.auth.utils import decode_session_token
from src.database import get_db
from src.exceptions import ForbiddenError
from src.notifications import service as notification_service
from src.users.models import User

DbDep = Annotated[AsyncSession, Depends(get_db)]


def read_session_payload(request: Request) -> dict | None:
    if hasattr(request.state, "session_payload"):
        return request.state.session_payload
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    return decode_session_token(token)


async def get_current_user(request: Request, db: DbDep) -> User:
    payload = read_session_payload(request)
    if payload is None:
        raise NotAuthenticated()
    try:
        user = await db.get(User, uuid.UUID(payload["sub"]))
    except (KeyError, ValueError):
        raise NotAuthenticated() from None
    if user is None or not user.is_active:
        raise NotAuthenticated()
    request.state.current_user = user
    request.state.csrf = payload["csrf"]
    request.state.unread_notifications = await notification_service.count_unread(db, user.id)
    return user


async def optional_user(request: Request, db: DbDep) -> User | None:
    try:
        return await get_current_user(request, db)
    except NotAuthenticated:
        return None


async def csrf_guard(request: Request) -> None:
    expected = getattr(request.state, "csrf", None)
    if expected is None:
        return
    provided = request.headers.get(CSRF_HEADER)
    content_type = request.headers.get("content-type", "").split(";")[0].lower()
    if not provided and content_type in {"application/x-www-form-urlencoded", "multipart/form-data"}:
        form = await request.form()
        provided = form.get(CSRF_FORM_FIELD)
    if not provided or not secrets.compare_digest(str(provided), str(expected)):
        raise ForbiddenError(detail="CSRF token mismatch")


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(optional_user)]
CsrfDep = Annotated[None, Depends(csrf_guard)]
