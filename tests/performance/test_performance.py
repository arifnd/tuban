from httpx2 import AsyncClient
from sqlalchemy import event, text

from src.database import engine
from src.pagination import clamp_per_page, paginate
from tests.helpers import login, make_user
from tests.tickets.helpers import make_ticket

HOT_PATH_INDEXES = (
    "tickets_status_updated_idx",
    "tickets_assignee_status_idx",
    "kb_articles_status_updated_idx",
    "notifications_user_read_created_idx",
    "activity_logs_created_idx",
)


def test_clamp_per_page() -> None:
    assert clamp_per_page(0) == 1
    assert clamp_per_page(-5) == 1
    assert clamp_per_page(1000) == 100
    assert clamp_per_page(25) == 25


def test_paginate_bounds() -> None:
    assert paginate(1, 25, 0)["total_pages"] == 1
    overflow = paginate(9, 25, 30)
    assert overflow["page"] == 2
    assert overflow["offset"] == 25


async def test_list_per_page_is_capped(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    await make_ticket(db, requester)
    await login(client, "u@example.com")
    assert (await client.get("/tickets", params={"per_page": "1000"})).status_code == 200


async def test_hot_path_indexes_exist(db) -> None:
    from src.config import settings

    if not settings.is_sqlite:
        import pytest

        pytest.skip("index introspection is SQLite-specific")

    result = await db.execute(text("SELECT name FROM sqlite_master WHERE type = 'index'"))
    names = {row[0] for row in result}
    for index in HOT_PATH_INDEXES:
        assert index in names, index


async def test_ticket_list_query_count_is_bounded(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    await make_ticket(db, requester)
    await login(client, "u@example.com")

    counter = {"selects": 0}

    def _before(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        if statement.lstrip().upper().startswith("SELECT"):
            counter["selects"] += 1

    event.listen(engine.sync_engine, "before_cursor_execute", _before)
    try:
        resp = await client.get("/tickets")
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _before)

    assert resp.status_code == 200
    assert counter["selects"] <= 12


async def test_kb_home_query_count_is_constant(client: AsyncClient, db) -> None:
    from src.kb import service as kb_service
    from src.kb.models import KbArticleStatus, KbArticleVisibility
    from tests.kb.helpers import make_article, make_editor

    editor = await make_editor(db, "editor@example.com")

    async def seed(count: int, tag: int) -> None:
        for index in range(count):
            category = await kb_service.create_category(db, editor, name=f"Cat {tag}-{index}")
            await make_article(
                db,
                editor,
                title=f"Art {tag}-{index}",
                category_id=category.id,
                status=KbArticleStatus.PUBLISHED,
                visibility=KbArticleVisibility.PUBLIC,
            )

    await seed(2, 1)
    await login(client, "editor@example.com")

    counter = {"selects": 0}

    def _before(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        if statement.lstrip().upper().startswith("SELECT"):
            counter["selects"] += 1

    event.listen(engine.sync_engine, "before_cursor_execute", _before)
    try:
        assert (await client.get("/kb")).status_code == 200
        first = counter["selects"]
        await seed(7, 2)
        counter["selects"] = 0
        assert (await client.get("/kb")).status_code == 200
        second = counter["selects"]
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _before)

    assert first > 0
    assert second == first


async def test_ticket_list_does_not_load_attachments(client: AsyncClient, db) -> None:
    from src.tickets.models import TicketAttachment

    requester = await make_user(db, "u@example.com")
    ticket = await make_ticket(db, requester)
    db.add(
        TicketAttachment(
            ticket_id=ticket.id,
            file_name="a.txt",
            file_path=f"tickets/{ticket.id}/a.txt",
            uploaded_by=requester.id,
            size_bytes=1,
            mime_type="text/plain",
        )
    )
    await db.flush()
    await login(client, "u@example.com")

    statements: list[str] = []

    def _capture(conn, cursor, statement, parameters, context, executemany):  # noqa: ANN001
        statements.append(statement)

    event.listen(engine.sync_engine, "before_cursor_execute", _capture)
    try:
        assert (await client.get("/tickets")).status_code == 200
    finally:
        event.remove(engine.sync_engine, "before_cursor_execute", _capture)

    assert not any("ticket_attachments" in statement for statement in statements)
