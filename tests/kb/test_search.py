from httpx2 import AsyncClient

from src.kb import service as kb_service
from src.kb.models import KbArticleStatus, KbArticleVisibility
from tests.kb.helpers import login, make_article, make_editor


async def test_search_matches_title_summary_body(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    await make_article(db, editor, title="Refund policy", body="nothing", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.PUBLIC)
    await make_article(db, editor, title="Other", summary="about refunds", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.PUBLIC)
    await make_article(db, editor, title="Third", body="a refund is possible", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.PUBLIC)

    await login(client, "member@example.com")
    resp = await client.get("/kb/search", params={"q": "refund"})
    assert resp.status_code == 200
    assert "policy" in resp.text
    assert "Other" in resp.text
    assert "Third" in resp.text


async def test_search_respects_visibility(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    await make_article(db, editor, title="Secret refunds", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.INTERNAL)

    await login(client, "member@example.com")
    resp = await client.get("/kb/search", params={"q": "refund"})
    assert resp.status_code == 200
    assert "Secret refunds" not in resp.text


async def test_tag_filter(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    tagged = await make_article(db, editor, title="Tagged doc", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.PUBLIC)
    await kb_service.set_article_tags(db, editor, tagged, ["billing"])
    await make_article(db, editor, title="Untagged doc", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.PUBLIC)

    await login(client, "member@example.com")
    resp = await client.get("/kb/search", params={"q": "doc", "tag": "billing"})
    assert resp.status_code == 200
    assert "Tagged" in resp.text
    assert "Untagged" not in resp.text


async def test_short_query_returns_hint(client: AsyncClient) -> None:
    await login(client, "member@example.com")
    resp = await client.get("/kb/search", params={"q": "a"})
    assert resp.status_code == 200


async def test_get_or_create_tags_is_idempotent(db) -> None:
    first = await kb_service.get_or_create_tags(db, ["Billing", "billing ", "Refunds"])
    await db.commit()
    second = await kb_service.get_or_create_tags(db, ["billing", "Refunds"])
    await db.commit()

    assert len(first) == 2
    assert {tag.id for tag in first} == {tag.id for tag in second}


async def test_tag_management_requires_editor(client: AsyncClient) -> None:
    await login(client, "member@example.com")
    resp = await client.get("/kb/tags")
    assert resp.status_code == 403


async def test_tag_page_lists_tags(client: AsyncClient, db) -> None:
    await kb_service.get_or_create_tags(db, ["networking"])
    await db.commit()
    await make_editor(db, "editor@example.com")

    await login(client, "editor@example.com")
    resp = await client.get("/kb/tags")
    assert resp.status_code == 200
    assert "networking" in resp.text
