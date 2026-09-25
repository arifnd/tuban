from httpx2 import AsyncClient

from src.settings import service as settings_service
from src.users.models import UserRole
from tests.tickets.helpers import csrf, login, make_user


async def test_carousel_requires_admin(client: AsyncClient, db) -> None:
    await make_user(db, "u@example.com")
    await login(client, "u@example.com")
    assert (await client.get("/carousel")).status_code == 403


async def test_admin_can_view_carousel(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")
    resp = await client.get("/carousel")
    assert resp.status_code == 200
    assert "carouselForm" in resp.text


async def test_admin_can_save_slides(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")

    resp = await client.post(
        "/carousel",
        data={
            "_csrf": csrf(client.cookies),
            "image_0": "https://cdn.example.com/a.jpg",
            "title_0": "Hello",
            "subtitle_0": "World",
        },
    )
    assert resp.status_code == 303
    assert settings_service.get("carousel_slides") == [{"image": "https://cdn.example.com/a.jpg", "title": "Hello", "subtitle": "World"}]


async def test_uploaded_slide_is_publicly_served(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")

    resp = await client.post(
        "/carousel",
        data={"_csrf": csrf(client.cookies), "title_0": "Pic"},
        files={"file_0": ("pic.png", b"png-bytes", "image/png")},
    )
    assert resp.status_code == 303

    slides = settings_service.get("carousel_slides")
    assert len(slides) == 1
    url = slides[0]["image"]
    assert url.startswith("/media/carousel/")

    client.cookies.clear()
    media = await client.get(url)
    assert media.status_code == 200
    assert media.content == b"png-bytes"


async def test_non_image_upload_rejected(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")

    resp = await client.post(
        "/carousel",
        data={"_csrf": csrf(client.cookies), "title_0": "Bad"},
        files={"file_0": ("evil.exe", b"MZ", "application/octet-stream")},
    )
    assert resp.status_code == 400


async def test_too_many_slides_rejected(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")

    data = {"_csrf": csrf(client.cookies)}
    for index in range(9):
        data[f"title_{index}"] = f"Slide {index}"
    resp = await client.post("/carousel", data=data)
    assert resp.status_code == 400


async def test_overlong_slide_text_rejected(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")

    resp = await client.post("/carousel", data={"_csrf": csrf(client.cookies), "title_0": "x" * 151})
    assert resp.status_code == 400


async def test_empty_rows_are_dropped(client: AsyncClient, db) -> None:
    await make_user(db, "admin@example.com", UserRole.ADMIN)
    await login(client, "admin@example.com")

    resp = await client.post(
        "/carousel",
        data={"_csrf": csrf(client.cookies), "title_0": "Kept", "image_1": "https://cdn.example.com/b.jpg"},
    )
    assert resp.status_code == 303
    assert settings_service.get("carousel_slides") == [{"image": "https://cdn.example.com/b.jpg", "title": "", "subtitle": ""}]
