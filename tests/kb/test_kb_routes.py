from httpx2 import AsyncClient

from src.kb import service as kb_service
from src.kb.models import KbArticleStatus, KbArticleVisibility
from tests.kb.helpers import csrf, login, make_article, make_editor


async def test_kb_home(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    category = await kb_service.create_category(db, editor, name="Guides")
    await make_article(db, editor, title="Guide one", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.PUBLIC, category_id=category.id)

    await login(client, "editor@example.com")
    assert (await client.get("/kb")).status_code == 200
    assert (await client.get("/kb/categories")).status_code == 200


async def test_article_list_filters(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    article = await make_article(db, editor, title="Filterable", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.PUBLIC)
    await kb_service.set_article_tags(db, editor, article, ["billing"])

    await login(client, "editor@example.com")
    assert (await client.get("/kb/articles", params={"q": "filter"})).status_code == 200
    assert (await client.get("/kb/articles", params={"article_status": "published"})).status_code == 200
    assert (await client.get("/kb/articles", params={"tag": "billing"})).status_code == 200
    assert (await client.get("/kb/articles", headers={"HX-Request": "true"})).status_code == 200


async def test_article_history_and_status_errors(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    article = await make_article(db, editor, title="History doc")
    await login(client, "editor@example.com")

    assert (await client.get(f"/kb/articles/{article.slug}/history")).status_code == 200
    resp = await client.post(f"/kb/articles/{article.slug}/status", data={"_csrf": csrf(client.cookies), "status": "bogus"})
    assert resp.status_code == 400
    resp = await client.post("/kb/articles", data={"_csrf": csrf(client.cookies), "title": ""})
    assert resp.status_code == 400


async def test_tags_pages_and_delete(client: AsyncClient, db) -> None:
    await make_editor(db, "editor@example.com")
    tags = await kb_service.get_or_create_tags(db, ["networking"])
    await db.commit()
    tag = tags[0]

    await login(client, "editor@example.com")
    assert (await client.get("/kb/tags")).status_code == 200
    assert (await client.get(f"/kb/tags/{tag.slug}")).status_code == 200
    resp = await client.post(f"/kb/tags/{tag.id}/delete", data={"_csrf": csrf(client.cookies)})
    assert resp.status_code == 303


async def test_category_error_branches(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    category = await kb_service.create_category(db, editor, name="Temp")
    await login(client, "editor@example.com")

    resp = await client.post("/kb/categories", data={"_csrf": csrf(client.cookies), "name": ""})
    assert resp.status_code == 400
    resp = await client.post(f"/kb/categories/{category.id}", data={"_csrf": csrf(client.cookies), "name": ""})
    assert resp.status_code == 400


async def test_feedback_and_view_count(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    article = await make_article(db, editor, title="Counted", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.PUBLIC)
    article_id = article.id

    await login(client, "member@example.com")
    await client.get(f"/kb/articles/{article.slug}")
    api = await client.get("/kb/articles", params={"q": "counted"})
    assert api.status_code == 200

    db.expire_all()
    from src.kb.models import KbArticle

    refreshed = await db.get(KbArticle, article_id)
    assert refreshed.view_count >= 1
