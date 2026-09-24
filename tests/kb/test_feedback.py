from httpx2 import AsyncClient
from sqlalchemy import select

from src.kb.models import KbArticleFeedback, KbArticleStatus, KbArticleVisibility
from tests.kb.helpers import csrf, login, make_article, make_editor


async def test_feedback_upsert_and_aggregate(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    article = await make_article(db, editor, title="Rate me", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.PUBLIC)

    await login(client, "member@example.com")
    resp = await client.post(
        f"/kb/articles/{article.slug}/feedback",
        data={"_csrf": csrf(client.cookies), "is_helpful": "1", "comment": "great"},
    )
    assert resp.status_code == 200
    assert "1 / 1" in resp.text

    resp = await client.post(
        f"/kb/articles/{article.slug}/feedback",
        data={"_csrf": csrf(client.cookies), "is_helpful": "0", "comment": "changed my mind"},
    )
    assert resp.status_code == 200
    assert "0 / 1" in resp.text

    rows = (await db.execute(select(KbArticleFeedback).where(KbArticleFeedback.article_id == article.id))).scalars().all()
    assert len(rows) == 1
    assert rows[0].is_helpful is False
    assert rows[0].comment == "changed my mind"


async def test_feedback_requires_authentication(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    article = await make_article(db, editor, title="No auth", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.PUBLIC)

    resp = await client.post(f"/kb/articles/{article.slug}/feedback", data={"is_helpful": "1"})
    assert resp.status_code == 401
