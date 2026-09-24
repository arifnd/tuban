from httpx2 import AsyncClient
from sqlalchemy import select

from src.settings import service as settings_service
from src.users.models import User, UserRole
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
    assert (await client.get("/settings")).status_code == 200

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
