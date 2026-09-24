from httpx2 import AsyncClient

from src.kb.models import KbArticleStatus, KbArticleVisibility
from tests.kb.helpers import make_article, make_editor
from tests.tickets.helpers import login, make_ticket, make_user


async def test_search_groups_kb_and_tickets(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    await make_article(db, editor, title="Refund policy", body="How refunds work", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.PUBLIC)
    requester = await make_user(db, "u@example.com")
    await make_ticket(db, requester, subject="Refund request")

    await login(client, "u@example.com")
    resp = await client.get("/search", params={"q": "refund"})
    assert resp.status_code == 200
    assert "policy" in resp.text
    assert "request" in resp.text

    api = await client.get("/search/api", params={"q": "refund"})
    body = api.json()
    assert body["total"] >= 2
    assert any(hit["kind"] == "kb" for hit in body["hits"])
    assert any(hit["kind"] == "ticket" for hit in body["hits"])


async def test_search_respects_visibility(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    await make_article(db, editor, title="Secret refunds", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.INTERNAL)

    await login(client, "u@example.com")
    resp = await client.get("/search", params={"q": "refund"})
    assert "Secret refunds" not in resp.text

    api = await client.get("/search/api", params={"q": "refund"})
    assert api.json()["total"] == 0


async def test_short_query_returns_nothing(client: AsyncClient, db) -> None:
    await make_user(db, "u@example.com")
    await login(client, "u@example.com")
    resp = await client.get("/search/api", params={"q": "a"})
    assert resp.json()["total"] == 0
    assert (await client.get("/search", params={"q": "a"})).status_code == 200


async def test_search_dropdown_partial(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    await make_article(db, editor, title="Password reset", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.PUBLIC)

    await login(client, "u@example.com")
    resp = await client.get("/search/partials/dropdown", params={"q": "password"})
    assert resp.status_code == 200
    assert "reset" in resp.text
