from httpx2 import AsyncClient

from src.users.models import UserRole
from tests.tickets.helpers import csrf, login, make_user


async def test_user_detail_and_filters(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    member = await make_user(db, "member@example.com")
    await login(client, "admin@example.com")

    assert (await client.get("/users")).status_code == 200
    assert (await client.get("/users", params={"role": "user", "active": "1"})).status_code == 200
    assert (await client.get("/users", params={"role": "bogus", "active": "9"})).status_code == 200
    assert (await client.get(f"/users/{member.id}")).status_code == 200


async def test_invalid_role_and_profile_error(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    member = await make_user(db, "member@example.com")
    await login(client, "admin@example.com")

    resp = await client.post(f"/users/{member.id}/role", data={"_csrf": csrf(client.cookies), "role": "bogus"})
    assert resp.status_code == 400

    await login(client, "member@example.com")
    resp = await client.post("/profile", data={"_csrf": csrf(client.cookies), "name": "   "})
    assert resp.status_code == 400
