from httpx2 import AsyncClient
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.tickets.models import Ticket
from tests.helpers import csrf, login, make_user
from tests.tickets.helpers import make_ticket


async def _load_ticket(db, ticket_id):
    return (await db.execute(select(Ticket).options(selectinload(Ticket.attachments)).where(Ticket.id == ticket_id))).scalar_one()


async def test_ticket_attachment_flow(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    await make_user(db, "other@example.com")
    ticket = await make_ticket(db, requester)
    ticket_id = ticket.id

    await login(client, "u@example.com")
    resp = await client.post(
        f"/tickets/{ticket_id}/attachments",
        data={"_csrf": csrf(client.cookies)},
        files={"file": ("log.txt", b"hello world", "text/plain")},
    )
    assert resp.status_code == 303

    db.expire_all()
    ticket = await _load_ticket(db, ticket_id)
    assert len(ticket.attachments) == 1
    key = ticket.attachments[0].file_path
    assert key.startswith(f"tickets/{ticket_id}/")

    resp = await client.get(f"/media/{key}")
    assert resp.status_code == 200
    assert resp.content == b"hello world"

    await login(client, "other@example.com")
    resp = await client.get(f"/media/{key}")
    assert resp.status_code == 404


async def test_blocked_file_type_rejected(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    ticket = await make_ticket(db, requester)
    await login(client, "u@example.com")

    resp = await client.post(
        f"/tickets/{ticket.id}/attachments",
        data={"_csrf": csrf(client.cookies)},
        files={"file": ("evil.exe", b"MZ", "application/octet-stream")},
    )
    assert resp.status_code == 400


async def test_comment_with_attachment(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    ticket = await make_ticket(db, requester)
    ticket_id = ticket.id
    await login(client, "u@example.com")

    resp = await client.post(
        f"/tickets/{ticket_id}/comments",
        data={"_csrf": csrf(client.cookies), "body": "see attached"},
        files={"file": ("note.txt", b"data", "text/plain")},
    )
    assert resp.status_code == 303

    db.expire_all()
    ticket = await _load_ticket(db, ticket_id)
    assert any(attachment.comment_id is not None for attachment in ticket.attachments)


async def test_create_ticket_with_attachments(client: AsyncClient, db) -> None:
    await make_user(db, "u@example.com")
    await login(client, "u@example.com")

    resp = await client.post(
        "/tickets",
        data={"_csrf": csrf(client.cookies), "subject": "Ticket with files"},
        files=[
            ("attachments", ("photo.png", b"pngbytes", "image/png")),
            ("attachments", ("report.pdf", b"pdfbytes", "application/pdf")),
        ],
    )
    assert resp.status_code == 303

    db.expire_all()
    ticket = (await db.execute(select(Ticket).options(selectinload(Ticket.attachments)).where(Ticket.subject == "Ticket with files"))).scalar_one()
    assert sorted(attachment.file_name for attachment in ticket.attachments) == ["photo.png", "report.pdf"]


async def test_create_ticket_rejects_blocked_attachment_inline(client: AsyncClient, db) -> None:
    await make_user(db, "u@example.com")
    await login(client, "u@example.com")

    resp = await client.post(
        "/tickets",
        data={"_csrf": csrf(client.cookies), "subject": "Blocked file"},
        files=[("attachments", ("evil.exe", b"MZ", "application/octet-stream"))],
    )
    assert resp.status_code == 400
    assert "Tipe file tidak didukung" in resp.text
    assert (await db.execute(select(Ticket).where(Ticket.subject == "Blocked file"))).scalar_one_or_none() is None


async def test_ticket_detail_shows_attachments(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    ticket = await make_ticket(db, requester)
    await login(client, "u@example.com")

    await client.post(
        f"/tickets/{ticket.id}/attachments",
        data={"_csrf": csrf(client.cookies)},
        files={"file": ("note.txt", b"data", "text/plain")},
    )
    resp = await client.get(f"/tickets/{ticket.id}")
    assert resp.status_code == 200
    assert "note.txt" in resp.text
