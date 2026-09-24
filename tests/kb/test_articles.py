from httpx2 import AsyncClient
from sqlalchemy import select

from src.kb import service as kb_service
from src.kb.markdown import render_markdown
from src.kb.models import KbArticle, KbArticleRevision, KbArticleStatus, KbArticleVisibility
from tests.kb.helpers import csrf, login, make_article, make_editor


async def test_create_draft_with_revision_and_tags(client: AsyncClient, db) -> None:
    await make_editor(db, "editor@example.com")
    await login(client, "editor@example.com")

    resp = await client.post(
        "/kb/articles",
        data={
            "_csrf": csrf(client.cookies),
            "title": "Getting Started",
            "summary": "Start here",
            "body": "Hello **world**",
            "visibility": "public",
            "action": "draft",
            "tags": "intro, basics",
        },
    )
    assert resp.status_code == 303

    article = (await db.execute(select(KbArticle).where(KbArticle.title == "Getting Started"))).scalar_one()
    assert article.slug == "getting-started"
    assert article.status == KbArticleStatus.DRAFT
    revisions = (await db.execute(select(KbArticleRevision).where(KbArticleRevision.article_id == article.id))).scalars().all()
    assert len(revisions) == 1
    assert revisions[0].revision_no == 1
    assert {tag.name for tag in article.tags} == {"intro", "basics"}


async def test_update_only_revisions_on_content_change(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    article = await make_article(db, editor, title="Doc", body="original")
    article_id = article.id
    slug = article.slug
    await login(client, "editor@example.com")

    base = {"_csrf": csrf(client.cookies), "title": "Doc", "summary": "", "body": "original", "visibility": "internal"}
    resp = await client.post(f"/kb/articles/{slug}", data=base)
    assert resp.status_code == 303

    revisions = (await db.execute(select(KbArticleRevision).where(KbArticleRevision.article_id == article_id))).scalars().all()
    assert revisions == []

    base["body"] = "changed"
    resp = await client.post(f"/kb/articles/{slug}", data=base)
    assert resp.status_code == 303

    revisions = (await db.execute(select(KbArticleRevision).where(KbArticleRevision.article_id == article_id))).scalars().all()
    assert len(revisions) == 1
    assert revisions[0].body == "changed"


async def test_publish_and_archive_transitions(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    article = await make_article(db, editor, title="Draft doc", status=KbArticleStatus.DRAFT)
    article_id = article.id
    slug = article.slug
    await login(client, "editor@example.com")

    resp = await client.post(f"/kb/articles/{slug}/status", data={"_csrf": csrf(client.cookies), "status": "published"})
    assert resp.status_code == 303
    db.expire_all()
    article = await db.get(KbArticle, article_id)
    assert article.status == KbArticleStatus.PUBLISHED
    assert article.published_at is not None

    resp = await client.post(f"/kb/articles/{slug}/status", data={"_csrf": csrf(client.cookies), "status": "draft"})
    assert resp.status_code == 303

    resp = await client.post(f"/kb/articles/{slug}/status", data={"_csrf": csrf(client.cookies), "status": "published"})
    assert resp.status_code == 303
    resp = await client.post(f"/kb/articles/{slug}/status", data={"_csrf": csrf(client.cookies), "status": "archived"})
    assert resp.status_code == 303
    resp = await client.post(f"/kb/articles/{slug}/status", data={"_csrf": csrf(client.cookies), "status": "draft"})
    assert resp.status_code == 400


async def test_hidden_articles_not_visible_to_regular_user(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    internal = await make_article(db, editor, title="Internal memo", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.INTERNAL)
    draft = await make_article(db, editor, title="Draft memo", status=KbArticleStatus.DRAFT, visibility=KbArticleVisibility.PUBLIC)

    await login(client, "member@example.com")
    assert (await client.get(f"/kb/articles/{internal.slug}")).status_code == 404
    assert (await client.get(f"/kb/articles/{draft.slug}")).status_code == 404


async def test_public_published_visible_to_regular_user(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    article = await make_article(db, editor, title="Public guide", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.PUBLIC)

    await login(client, "member@example.com")
    resp = await client.get(f"/kb/articles/{article.slug}")
    assert resp.status_code == 200
    assert "Public guide" in resp.text


def test_markdown_renderer_strips_scripts() -> None:
    html = render_markdown("<script>alert(1)</script>\n\nThis is **bold**.")
    assert "<script>" not in html
    assert "<strong>bold</strong>" in html


async def test_markdown_rendered_and_sanitized_on_page(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    body = "<script>alert(1)</script>\n\nThis is **bold**."
    article = await kb_service.create_article(db, editor, title="Safe doc", body=body, visibility=KbArticleVisibility.PUBLIC, status=KbArticleStatus.PUBLISHED)

    await login(client, "editor@example.com")
    resp = await client.get(f"/kb/articles/{article.slug}")
    assert resp.status_code == 200
    assert "<script>alert(1)</script>" not in resp.text
    assert "<strong>bold</strong>" in resp.text


async def test_restore_revision_adds_history(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    article = await kb_service.create_article(db, editor, title="Versioned", body="v1")
    article_id = article.id
    await kb_service.update_article(db, editor, article, title="Versioned", summary=None, body="v2", category_id=None, visibility=KbArticleVisibility.INTERNAL)
    revisions = await kb_service.list_revisions(db, article)
    first = [r for r in revisions if r.body == "v1"][0]

    await login(client, "editor@example.com")
    resp = await client.post(f"/kb/articles/{article.slug}/restore/{first.id}", data={"_csrf": csrf(client.cookies)})
    assert resp.status_code == 303

    db.expire_all()
    article = await db.get(KbArticle, article_id)
    assert article.body == "v1"
    revisions = await kb_service.list_revisions(db, article)
    assert len(revisions) == 3
