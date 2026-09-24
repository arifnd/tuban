import uuid

from httpx2 import AsyncClient
from sqlalchemy import select

from src.activity.models import ActivityLog
from src.auth.utils import decode_session_token
from src.users.models import User, UserRole


def _csrf(cookies) -> str:
    return decode_session_token(cookies["app_session"])["csrf"]


async def _login(client: AsyncClient, email: str) -> None:
    client.cookies.clear()
    resp = await client.post("/auth/dev-login", json={"email": email})
    assert resp.status_code == 303


async def _user_id(db, email: str) -> uuid.UUID:
    return (await db.execute(select(User.id).where(User.email == email))).scalar_one()


async def test_users_list_requires_admin(client: AsyncClient) -> None:
    await _login(client, "member@example.com")
    resp = await client.get("/users")
    assert resp.status_code == 403


async def test_users_list_requires_authentication(client: AsyncClient) -> None:
    resp = await client.get("/users", headers={"accept": "text/html"})
    assert resp.status_code == 303
    assert "/auth/login" in resp.headers["location"]

    resp = await client.get("/users", headers={"accept": "application/json"})
    assert resp.status_code == 401


async def test_admin_can_list_users(client: AsyncClient) -> None:
    await _login(client, "member@example.com")
    await _login(client, "admin@example.com")
    resp = await client.get("/users")
    assert resp.status_code == 200


async def test_admin_can_change_role(client: AsyncClient, db) -> None:
    await _login(client, "member@example.com")
    await _login(client, "admin@example.com")
    member_id = await _user_id(db, "member@example.com")

    resp = await client.post(
        f"/users/{member_id}/role",
        data={"_csrf": _csrf(client.cookies), "role": "agent"},
    )
    assert resp.status_code == 303

    db.expire_all()
    member = await db.get(User, member_id)
    assert member.role == UserRole.AGENT


async def test_role_change_writes_activity_log(client: AsyncClient, db) -> None:
    await _login(client, "member@example.com")
    await _login(client, "admin@example.com")
    member_id = await _user_id(db, "member@example.com")

    resp = await client.post(f"/users/{member_id}/role", data={"_csrf": _csrf(client.cookies), "role": "agent"})
    assert resp.status_code == 303

    count = (await db.execute(select(ActivityLog).where(ActivityLog.entity_id == member_id))).scalars().all()
    assert len(count) >= 1
    assert count[-1].new_data == {"role": "agent"}


async def test_last_admin_cannot_be_demoted(client: AsyncClient, db) -> None:
    await _login(client, "member@example.com")
    await _login(client, "admin@example.com")
    admin_id = await _user_id(db, "admin@example.com")

    resp = await client.post(f"/users/{admin_id}/role", data={"_csrf": _csrf(client.cookies), "role": "user"})
    assert resp.status_code == 400


async def test_last_admin_cannot_self_deactivate(client: AsyncClient, db) -> None:
    await _login(client, "member@example.com")
    await _login(client, "admin@example.com")
    admin_id = await _user_id(db, "admin@example.com")

    resp = await client.post(f"/users/{admin_id}/active", data={"_csrf": _csrf(client.cookies)})
    assert resp.status_code == 400


async def test_deactivated_user_cannot_login(client: AsyncClient, db) -> None:
    await _login(client, "member@example.com")
    member_id = await _user_id(db, "member@example.com")

    # Deactivate directly (bypassing the last-admin guard, member is not admin).
    member = await db.get(User, member_id)
    member.is_active = False
    await db.commit()
    await db.refresh(member)

    client.cookies.clear()
    resp = await client.post("/auth/dev-login", json={"email": "member@example.com"})
    assert resp.status_code == 403


async def test_profile_update(client: AsyncClient, db) -> None:
    await _login(client, "member@example.com")
    resp = await client.get("/profile")
    assert resp.status_code == 200

    resp = await client.post("/profile", data={"_csrf": _csrf(client.cookies), "name": "New Name"})
    assert resp.status_code == 303

    member_id = await _user_id(db, "member@example.com")
    db.expire_all()
    member = await db.get(User, member_id)
    assert member.name == "New Name"
