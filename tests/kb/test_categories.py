from httpx2 import AsyncClient
from sqlalchemy import select

from src.kb import service as kb_service
from src.kb.models import KbCategory
from tests.kb.helpers import csrf, get_category, login, make_article, make_editor


async def test_categories_requires_editor(client: AsyncClient) -> None:
    await login(client, "member@example.com")
    resp = await client.get("/kb/categories")
    assert resp.status_code == 403


async def test_create_and_update_category(client: AsyncClient, db) -> None:
    await make_editor(db, "editor@example.com")
    await login(client, "editor@example.com")

    resp = await client.post(
        "/kb/categories",
        data={"_csrf": csrf(client.cookies), "name": "Billing", "description": "Money", "position": "1"},
    )
    assert resp.status_code == 303

    category = await get_category(db, "Billing")
    category_id = category.id
    assert category.slug == "billing"
    assert category.description == "Money"

    resp = await client.post(
        f"/kb/categories/{category_id}",
        data={"_csrf": csrf(client.cookies), "name": "Payments", "description": "", "position": "2"},
    )
    assert resp.status_code == 303
    db.expire_all()
    category = await db.get(KbCategory, category_id)
    assert category.name == "Payments"
    assert category.slug == "payments"


async def test_delete_blocked_when_articles_exist(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    category = await kb_service.create_category(db, editor, name="Docs")
    category_id = category.id
    await make_article(db, editor, title="In docs", category_id=category_id)
    await login(client, "editor@example.com")

    resp = await client.post(f"/kb/categories/{category_id}/delete", data={"_csrf": csrf(client.cookies)})
    assert resp.status_code == 409


async def test_delete_empty_category(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    category = await kb_service.create_category(db, editor, name="Temp")
    category_id = category.id
    await login(client, "editor@example.com")

    resp = await client.post(f"/kb/categories/{category_id}/delete", data={"_csrf": csrf(client.cookies)})
    assert resp.status_code == 303
    db.expire_all()
    assert await db.get(KbCategory, category_id) is None


async def test_duplicate_slug_gets_suffix(client: AsyncClient, db) -> None:
    await make_editor(db, "editor@example.com")
    await login(client, "editor@example.com")

    for _ in range(2):
        resp = await client.post("/kb/categories", data={"_csrf": csrf(client.cookies), "name": "Same Name", "description": "", "position": "0"})
        assert resp.status_code == 303

    slugs = sorted((await db.execute(select(KbCategory.slug))).scalars().all())
    assert slugs == ["same-name", "same-name-2"]
