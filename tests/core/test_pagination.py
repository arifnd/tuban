from httpx2 import AsyncClient

from src.activity import service as activity_service
from src.notifications import service as notification_service
from src.pagination import Page, clamp_per_page, paginate
from src.users.models import UserRole
from tests.helpers import login, make_user
from tests.kb.helpers import make_article, make_editor
from tests.tickets.helpers import make_ticket


def _page_indicator(html: str, page: int, total_pages: int) -> str:
    return f"Halaman {page} dari {total_pages}"


def test_paginate_clamps_out_of_range_pages() -> None:
    assert paginate(0, 10, 25)["page"] == 1
    assert paginate(0, 10, 25)["offset"] == 0
    assert paginate(-5, 10, 25)["page"] == 1
    assert paginate(999, 10, 25)["page"] == 3
    assert paginate(999, 10, 25)["offset"] == 20
    assert paginate(1, 10, 0)["total_pages"] == 1


def test_page_create_and_context() -> None:
    page = Page.create(999, 10, ["z"], 25)
    assert (page.page, page.offset, page.total_pages) == (3, 20, 3)
    context = page.as_context("items", extra="x")
    assert context["items"] == ["z"]
    assert context["page"] == 3
    assert context["total"] == 25
    assert context["total_pages"] == 3
    assert context["extra"] == "x"
    assert clamp_per_page(0) == 1
    assert clamp_per_page(1000) == 100


async def test_users_pagination_clamps(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await make_user(db, "m1@example.com")
    await make_user(db, "m2@example.com")
    await login(client, "admin@example.com")

    first = await client.get("/users", params={"page": 0, "per_page": 1})
    assert _page_indicator(first.text, 1, 2) in first.text
    negative = await client.get("/users", params={"page": -3, "per_page": 1})
    assert _page_indicator(negative.text, 1, 2) in negative.text
    last = await client.get("/users", params={"page": 99, "per_page": 1})
    assert _page_indicator(last.text, 2, 2) in last.text


async def test_tickets_pagination_clamps(client: AsyncClient, db) -> None:
    requester = await make_user(db, "r@example.com")
    await make_ticket(db, requester, subject="First ticket")
    await make_ticket(db, requester, subject="Second ticket")
    await login(client, "r@example.com")

    first = await client.get("/tickets", params={"page": 0, "per_page": 1})
    assert _page_indicator(first.text, 1, 2) in first.text
    last = await client.get("/tickets", params={"page": 99, "per_page": 1})
    assert _page_indicator(last.text, 2, 2) in last.text


async def test_kb_pagination_clamps(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    await make_article(db, editor, title="One")
    await make_article(db, editor, title="Two")
    await login(client, "editor@example.com")

    first = await client.get("/kb/articles", params={"page": 0, "per_page": 1})
    assert _page_indicator(first.text, 1, 2) in first.text
    last = await client.get("/kb/articles", params={"page": 99, "per_page": 1})
    assert _page_indicator(last.text, 2, 2) in last.text


async def test_activity_pagination_clamps(client: AsyncClient, db) -> None:
    admin = await make_user(db, "admin@example.com", UserRole.ADMIN)
    await activity_service.log(db, user_id=admin.id, action="create", entity_type="x")
    await activity_service.log(db, user_id=admin.id, action="update", entity_type="y")
    await login(client, "admin@example.com")

    first = await client.get("/activity", params={"page": 0, "per_page": 1})
    assert _page_indicator(first.text, 1, 2) in first.text
    last = await client.get("/activity", params={"page": 99, "per_page": 1})
    assert _page_indicator(last.text, 2, 2) in last.text


async def test_notifications_pagination_clamps(client: AsyncClient, db) -> None:
    user = await make_user(db, "n@example.com")
    await notification_service.create_notification(db, user_id=user.id, type="t", title="One")
    await notification_service.create_notification(db, user_id=user.id, type="t", title="Two")
    await login(client, "n@example.com")

    first = await client.get("/notifications", params={"page": 0, "per_page": 1})
    assert _page_indicator(first.text, 1, 2) in first.text
    last = await client.get("/notifications", params={"page": 99, "per_page": 1})
    assert _page_indicator(last.text, 2, 2) in last.text
