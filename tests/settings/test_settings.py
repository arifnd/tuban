from httpx2 import AsyncClient
from sqlalchemy import select

from src.kb.models import KbArticleStatus, KbArticleVisibility
from src.settings import service as settings_service
from src.users.models import User, UserRole
from tests.kb.helpers import make_article, make_editor
from tests.tickets.helpers import csrf, login, make_user

BASE_FORM = {
    "app_name": "Batik Helpdesk",
    "default_language": "id",
    "sla_urgent_hours": "4",
    "sla_high_hours": "8",
    "sla_normal_hours": "24",
    "sla_low_hours": "72",
    "upload_max_size_mb": "20",
    "allowed_extensions": "png, jpg, pdf",
    "open_registration": "1",
}


async def test_settings_requires_admin(client: AsyncClient, db) -> None:
    await make_user(db, "u@example.com")
    await login(client, "u@example.com")
    assert (await client.get("/settings")).status_code == 403

    await make_user(db, "agent@example.com", UserRole.AGENT)
    await login(client, "agent@example.com")
    assert (await client.get("/settings")).status_code == 403


async def test_admin_can_view_and_update_settings(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")
    page = await client.get("/settings")
    assert page.status_code == 200
    assert 'name="theme_color"' in page.text
    assert 'value="green"' in page.text

    form = dict(BASE_FORM)
    form.update(
        {
            "_csrf": csrf(client.cookies),
            "app_name": "Batik Desk",
            "default_language": "en",
            "upload_max_size_mb": "5",
            "allowed_extensions": "png, pdf",
            "require_approval": "1",
        }
    )
    resp = await client.post("/settings", data=form)
    assert resp.status_code == 303

    assert settings_service.get("app_name") == "Batik Desk"
    assert settings_service.get("default_language") == "en"
    assert settings_service.get("upload_max_size") == 5 * 1024 * 1024
    assert settings_service.get("allowed_extensions") == ["png", "pdf"]
    assert settings_service.get("require_approval") is True

    page = await client.get("/settings?saved=1")
    assert page.status_code == 200
    assert "Settings saved." in page.text

    from src.templating import t

    assert t("nav.dashboard") == "Dashboard"


async def test_invalid_settings_rejected(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")
    token = csrf(client.cookies)

    empty_name = dict(BASE_FORM, _csrf=token, app_name="")
    assert (await client.post("/settings", data=empty_name)).status_code == 400

    bad_language = dict(BASE_FORM, _csrf=token, default_language="fr")
    assert (await client.post("/settings", data=bad_language)).status_code == 400

    bad_extensions = dict(BASE_FORM, _csrf=token, allowed_extensions="")
    assert (await client.post("/settings", data=bad_extensions)).status_code == 400


async def test_contact_info_saved_and_shown_on_landing(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")

    form = dict(
        BASE_FORM,
        _csrf=csrf(client.cookies),
        contact_email="support@example.com",
        contact_phone="+62 812 0000",
        contact_address="Jl. Merdeka 1",
        social_facebook="https://facebook.com/batik",
        social_instagram="https://instagram.com/batik",
    )
    assert (await client.post("/settings", data=form)).status_code == 303
    assert settings_service.get("contact_email") == "support@example.com"
    assert settings_service.get("social_facebook") == "https://facebook.com/batik"

    client.cookies.clear()
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "support@example.com" in resp.text
    assert "+62 812 0000" in resp.text
    assert "Jl. Merdeka 1" in resp.text
    assert "https://facebook.com/batik" in resp.text
    assert "https://instagram.com/batik" in resp.text
    assert "text-[#1877F2]" in resp.text
    assert "text-[#E4405F]" in resp.text


async def test_carousel_images_shown_on_landing(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")

    form = dict(
        BASE_FORM,
        _csrf=csrf(client.cookies),
        carousel_image_1="https://cdn.example.com/one.jpg",
        carousel_image_2="https://cdn.example.com/two.jpg",
    )
    assert (await client.post("/settings", data=form)).status_code == 303
    assert settings_service.get("carousel_image_1") == "https://cdn.example.com/one.jpg"

    client.cookies.clear()
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "https://cdn.example.com/one.jpg" in resp.text
    assert "https://cdn.example.com/two.jpg" in resp.text


async def test_landing_shows_only_public_articles(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    await make_article(db, editor, title="Public Guide", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.PUBLIC)
    await make_article(db, editor, title="Internal Runbook", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.INTERNAL)
    await make_article(db, editor, title="Draft Notes", status=KbArticleStatus.DRAFT, visibility=KbArticleVisibility.PUBLIC)

    resp = await client.get("/")
    assert resp.status_code == 200
    assert "Public Guide" in resp.text
    assert "Internal Runbook" not in resp.text
    assert "Draft Notes" not in resp.text


async def test_landing_category_counts_exclude_non_public(db) -> None:
    from src.kb import service as kb_service

    editor = await make_editor(db, "editor@example.com")
    category = await kb_service.create_category(db, editor, name="Guides")
    await make_article(db, editor, title="Pub", category_id=category.id, status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.PUBLIC)
    await make_article(db, editor, title="Int", category_id=category.id, status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.INTERNAL)

    public_categories = await kb_service.list_categories(db, viewer=None)
    assert next(c for c in public_categories if c.name == "Guides").article_count == 1

    editor_categories = await kb_service.list_categories(db, viewer=editor)
    assert next(c for c in editor_categories if c.name == "Guides").article_count == 2


async def test_invalid_contact_email_rejected(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")

    form = dict(BASE_FORM, _csrf=csrf(client.cookies), contact_email="not-an-email")
    assert (await client.post("/settings", data=form)).status_code == 400


async def test_invalid_social_url_rejected(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")

    form = dict(BASE_FORM, _csrf=csrf(client.cookies), social_facebook="facebook.com/batik")
    assert (await client.post("/settings", data=form)).status_code == 400


async def test_theme_color_saved_and_applied(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")

    form = dict(BASE_FORM, _csrf=csrf(client.cookies), theme_color="blue")
    assert (await client.post("/settings", data=form)).status_code == 303
    assert settings_service.get("theme_color") == "blue"

    client.cookies.clear()
    resp = await client.get("/")
    assert resp.status_code == 200
    assert "--brand-600: 37 99 235" in resp.text


async def test_invalid_theme_color_rejected(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")

    form = dict(BASE_FORM, _csrf=csrf(client.cookies), theme_color="magenta")
    assert (await client.post("/settings", data=form)).status_code == 400


async def test_open_registration_can_be_disabled(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")

    form = dict(BASE_FORM, _csrf=csrf(client.cookies))
    form.pop("open_registration")
    assert (await client.post("/settings", data=form)).status_code == 303

    client.cookies.clear()
    resp = await client.post("/auth/dev-login", json={"email": "newcomer@example.com"})
    assert resp.status_code == 403


async def test_require_approval_creates_inactive_user(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")

    form = dict(BASE_FORM, _csrf=csrf(client.cookies), require_approval="1")
    assert (await client.post("/settings", data=form)).status_code == 303

    client.cookies.clear()
    resp = await client.post("/auth/dev-login", json={"email": "pending@example.com"})
    assert resp.status_code == 403

    from src.database import SessionFactory

    async with SessionFactory() as session:
        pending = (await session.execute(select(User).where(User.email == "pending@example.com"))).scalar_one()
    assert pending.is_active is False
