from httpx2 import AsyncClient
from sqlalchemy import select

from src.activity.models import ActivityLog
from src.users.models import UserRole
from tests.tickets.helpers import csrf, login, make_user


async def test_activity_admin_only(client: AsyncClient, db) -> None:
    await make_user(db, "u@example.com")
    await login(client, "u@example.com")
    assert (await client.get("/activity")).status_code == 403

    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")
    assert (await client.get("/activity")).status_code == 200


async def test_ticket_events_are_logged(client: AsyncClient, db) -> None:
    await make_user(db, "u@example.com")
    await make_user(db, "agent@example.com", UserRole.AGENT)

    await login(client, "u@example.com")
    await client.post("/tickets", data={"_csrf": csrf(client.cookies), "subject": "Log me please"})

    rows = (await db.execute(select(ActivityLog).where(ActivityLog.entity_type == "tickets"))).scalars().all()
    assert len(rows) >= 1
    assert rows[0].action == "create"
