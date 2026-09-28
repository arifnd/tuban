from httpx2 import AsyncClient

from src.kb import service as kb_service
from src.kb.models import KbArticleStatus, KbArticleVisibility
from tests.helpers import csrf, login, make_user
from tests.kb.helpers import make_article, make_editor


async def test_not_found_renders_html(client: AsyncClient) -> None:
    resp = await client.get("/does-not-exist", headers={"accept": "text/html"})
    assert resp.status_code == 404
    assert resp.headers["content-type"].startswith("text/html")


async def test_forbidden_renders_html(client: AsyncClient, db) -> None:
    await make_user(db, "member@example.com")
    await login(client, "member@example.com")
    resp = await client.get("/users", headers={"accept": "text/html"})
    assert resp.status_code == 403
    assert resp.headers["content-type"].startswith("text/html")


async def test_bad_request_html_for_browser_json_for_api(client: AsyncClient, db) -> None:
    await make_user(db, "member@example.com")
    await login(client, "member@example.com")
    token = csrf(client.cookies)

    html = await client.post("/profile", data={"_csrf": token, "name": "   "}, headers={"accept": "text/html"})
    assert html.status_code == 400
    assert html.headers["content-type"].startswith("text/html")

    api = await client.post("/profile", data={"_csrf": token, "name": "   "}, headers={"accept": "application/json"})
    assert api.status_code == 400
    assert api.headers["content-type"].startswith("application/json")
    assert api.json()["detail"] == "Name is required"


async def test_conflict_renders_html(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    category = await kb_service.create_category(db, editor, name="Busy")
    await make_article(db, editor, title="In category", category_id=category.id, status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.PUBLIC)
    await login(client, "editor@example.com")

    resp = await client.post(f"/kb/categories/{category.id}/delete", data={"_csrf": csrf(client.cookies)}, headers={"accept": "text/html"})
    assert resp.status_code == 409
    assert resp.headers["content-type"].startswith("text/html")


async def test_generic_4xx_fallback_renders_html(client: AsyncClient) -> None:
    resp = await client.post("/auth/dev-login", json={"email": "bad"}, headers={"accept": "text/html"})
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("text/html")
