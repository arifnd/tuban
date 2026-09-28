from httpx2 import AsyncClient

from src.auth import service as auth_service
from src.auth.utils import decode_session_token
from src.users.models import User, UserRole

__all__ = ["csrf", "login", "make_user"]


def csrf(cookies) -> str:
    return decode_session_token(cookies["app_session"])["csrf"]


async def login(client: AsyncClient, email: str) -> None:
    client.cookies.clear()
    resp = await client.post("/auth/dev-login", json={"email": email})
    assert resp.status_code == 303


async def make_user(db, email: str, role: UserRole = UserRole.USER) -> User:
    user = await auth_service.dev_login(db, email)
    user.role = role
    await db.commit()
    await db.refresh(user)
    return user
