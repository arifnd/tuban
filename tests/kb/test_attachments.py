from httpx2 import AsyncClient

from src.kb.models import KbArticle, KbArticleStatus, KbArticleVisibility
from tests.kb.helpers import csrf, login, make_article, make_editor


async def test_upload_and_media_authorization(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    article = await make_article(db, editor, title="With files", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.INTERNAL)
    article_id = article.id
    slug = article.slug

    await login(client, "editor@example.com")
    resp = await client.post(
        f"/kb/articles/{slug}/attachments",
        data={"_csrf": csrf(client.cookies)},
        files={"file": ("note.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 303

    db.expire_all()
    article = await db.get(KbArticle, article_id)
    assert len(article.attachments) == 1
    key = article.attachments[0].file_path
    assert key.startswith(f"kb/{article_id}/")

    # unauthenticated media fetch is rejected
    client.cookies.clear()
    resp = await client.get(f"/media/{key}")
    assert resp.status_code == 401

    # a regular user cannot fetch an internal article's media
    await login(client, "member@example.com")
    resp = await client.get(f"/media/{key}")
    assert resp.status_code == 404

    # the editor can fetch it
    await login(client, "editor@example.com")
    resp = await client.get(f"/media/{key}")
    assert resp.status_code == 200
    assert resp.content == b"hello world"


async def test_blocked_file_type_rejected(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    article = await make_article(db, editor, title="Blocked type")
    article_id = article.id
    slug = article.slug
    await login(client, "editor@example.com")

    resp = await client.post(
        f"/kb/articles/{slug}/attachments",
        data={"_csrf": csrf(client.cookies)},
        files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
    )
    assert resp.status_code == 400

    db.expire_all()
    article = await db.get(KbArticle, article_id)
    assert article.attachments == []


async def test_delete_attachment(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    article = await make_article(db, editor, title="Delete me")
    article_id = article.id
    slug = article.slug
    await login(client, "editor@example.com")

    await client.post(
        f"/kb/articles/{slug}/attachments",
        data={"_csrf": csrf(client.cookies)},
        files={"file": ("a.txt", b"data", "text/plain")},
    )
    db.expire_all()
    article = await db.get(KbArticle, article_id)
    attachment_id = article.attachments[0].id

    resp = await client.post(f"/kb/articles/{slug}/attachments/{attachment_id}/delete", data={"_csrf": csrf(client.cookies)})
    assert resp.status_code == 303

    db.expire_all()
    article = await db.get(KbArticle, article_id)
    assert article.attachments == []
