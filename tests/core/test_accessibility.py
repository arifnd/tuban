from httpx2 import AsyncClient

from src.users.models import UserRole
from tests.helpers import login, make_user


async def test_theme_radios_have_accessible_names(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")
    resp = await client.get("/settings")
    assert resp.status_code == 200
    assert 'aria-label="green"' in resp.text
    assert 'for="storage_backend"' in resp.text
    assert 'id="storage_backend"' in resp.text


async def test_table_headers_have_scope(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")
    resp = await client.get("/activity")
    assert resp.status_code == 200
    assert '<th scope="col"' in resp.text


async def test_active_nav_has_aria_current(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")
    resp = await client.get("/kb")
    assert resp.status_code == 200
    assert 'aria-current="page"' in resp.text
