from httpx2 import AsyncClient

from src.tickets.models import Ticket
from tests.tickets.helpers import csrf, login, make_ticket, make_user


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
    ticket = await db.get(Ticket, ticket_id)
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
    ticket = await db.get(Ticket, ticket_id)
    assert any(attachment.comment_id is not None for attachment in ticket.attachments)
