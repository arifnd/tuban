from httpx2 import AsyncClient
from sqlalchemy import event, text

from src.database import engine
from src.pagination import clamp_per_page, paginate
from tests.tickets.helpers import login, make_ticket, make_user

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
