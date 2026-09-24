from httpx2 import AsyncClient

from src.tickets import service as ticket_service
from src.users.models import UserRole
from tests.tickets.helpers import csrf, login, make_ticket, make_user


async def test_categories_requires_editor(client: AsyncClient, db) -> None:
    await make_user(db, "u@example.com")
    await login(client, "u@example.com")
    assert (await client.get("/tickets/categories")).status_code == 403


async def test_category_crud_and_delete_guard(client: AsyncClient, db) -> None:
    await make_user(db, "agent@example.com", UserRole.AGENT)
    requester = await make_user(db, "u@example.com")
    await login(client, "agent@example.com")

    resp = await client.post("/tickets/categories", data={"_csrf": csrf(client.cookies), "name": "Billing", "position": "1"})
    assert resp.status_code == 303
    category = (await ticket_service.list_categories(db))[0]
    assert category.name == "Billing"

    resp = await client.post(f"/tickets/categories/{category.id}", data={"_csrf": csrf(client.cookies), "name": "Payments", "position": "2"})
    assert resp.status_code == 303

    await make_ticket(db, requester, category_id=category.id)
    resp = await client.post(f"/tickets/categories/{category.id}/delete", data={"_csrf": csrf(client.cookies)})
    assert resp.status_code == 409


async def test_delete_empty_category(client: AsyncClient, db) -> None:
    await make_user(db, "agent@example.com", UserRole.AGENT)
    await login(client, "agent@example.com")

    resp = await client.post("/tickets/categories", data={"_csrf": csrf(client.cookies), "name": "Temp", "position": "0"})
    assert resp.status_code == 303
    category = (await ticket_service.list_categories(db))[0]

    resp = await client.post(f"/tickets/categories/{category.id}/delete", data={"_csrf": csrf(client.cookies)})
    assert resp.status_code == 303
    assert await ticket_service.list_categories(db) == []
