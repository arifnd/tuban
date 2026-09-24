import uuid

from httpx2 import AsyncClient
from sqlalchemy import select

from src.kb.models import KbArticleStatus, KbArticleVisibility
from src.tickets.models import Ticket, TicketComment, TicketStatus
from src.users.models import UserRole
from tests.kb.helpers import make_article, make_editor
from tests.tickets.helpers import csrf, login, make_ticket, make_user


async def test_ticket_not_found(client: AsyncClient, db) -> None:
    await make_user(db, "u@example.com")
    await login(client, "u@example.com")
    assert (await client.get(f"/tickets/{uuid.uuid4()}")).status_code == 404


async def test_agents_endpoint_and_claim(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    agent = await make_user(db, "agent@example.com", UserRole.AGENT)
    ticket = await make_ticket(db, requester)
    ticket_id = ticket.id
    await login(client, "agent@example.com")

    resp = await client.get("/tickets/agents")
    assert resp.status_code == 200
    assert any(item["name"] == agent.name for item in resp.json())

    assert (await client.post(f"/tickets/{ticket_id}/claim", data={"_csrf": csrf(client.cookies)})).status_code == 303
    db.expire_all()
    assert (await db.get(Ticket, ticket_id)).assignee_id == agent.id


async def test_unassign_and_priority_error(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    await make_user(db, "agent@example.com", UserRole.AGENT)
    ticket = await make_ticket(db, requester)
    ticket_id = ticket.id
    await login(client, "agent@example.com")

    assert (await client.post(f"/tickets/{ticket_id}/assign", data={"_csrf": csrf(client.cookies), "assignee_id": ""})).status_code == 303
    assert (await client.post(f"/tickets/{ticket_id}/priority", data={"_csrf": csrf(client.cookies), "priority": "nope"})).status_code == 400


async def test_comment_delete_permissions(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    other = await make_user(db, "other@example.com")
    ticket = await make_ticket(db, requester)
    ticket_id = ticket.id

    await login(client, "u@example.com")
    await client.post(f"/tickets/{ticket_id}/comments", data={"_csrf": csrf(client.cookies), "body": "hello"})
    comment = (await db.execute(select(TicketComment).where(TicketComment.ticket_id == ticket_id))).scalar_one()
    comment_id = comment.id

    await login(client, "other@example.com")
    other_ticket = await make_ticket(db, other, subject="Other")
    assert (await client.post(f"/tickets/{ticket_id}/comments/{comment_id}/delete", data={"_csrf": csrf(client.cookies)})).status_code == 403
    assert other_ticket is not None

    await login(client, "u@example.com")
    assert (await client.post(f"/tickets/{ticket_id}/comments/{comment_id}/delete", data={"_csrf": csrf(client.cookies)})).status_code == 303


async def test_category_error_branches(client: AsyncClient, db) -> None:
    await make_user(db, "agent@example.com", UserRole.AGENT)
    await login(client, "agent@example.com")
    assert (await client.post("/tickets/categories", data={"_csrf": csrf(client.cookies), "name": ""})).status_code == 400


async def test_list_sort_variants_and_related(client: AsyncClient, db) -> None:
    editor = await make_editor(db, "editor@example.com")
    await make_article(db, editor, title="Printer troubleshooting", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.PUBLIC)
    requester = await make_user(db, "u@example.com")
    await make_ticket(db, requester, subject="Printer problem")

    await login(client, "u@example.com")
    for sort in ("updated", "created", "priority", "sla"):
        assert (await client.get("/tickets", params={"sort": sort})).status_code == 200

    detail = await client.get(f"/tickets/{(await make_ticket(db, requester, subject='Another')).id}")
    assert detail.status_code == 200


async def test_workflow_non_member_forbidden(client: AsyncClient, db) -> None:
    requester = await make_user(db, "u@example.com")
    await make_user(db, "other@example.com")
    ticket = await make_ticket(db, requester)
    await login(client, "other@example.com")
    resp = await client.post(f"/tickets/{ticket.id}/status", data={"_csrf": csrf(client.cookies), "status": "closed"})
    assert resp.status_code == 403
    assert TicketStatus is not None
