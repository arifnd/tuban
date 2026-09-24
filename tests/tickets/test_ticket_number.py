from httpx2 import AsyncClient
from sqlalchemy import select

from src.tickets.models import Ticket
from tests.tickets.helpers import csrf, login, make_user


async def test_ticket_numbers_are_unique_and_sequential(client: AsyncClient, db) -> None:
    await make_user(db, "u@example.com")
    await login(client, "u@example.com")

    for index in range(3):
        resp = await client.post("/tickets", data={"_csrf": csrf(client.cookies), "subject": f"Ticket {index}"})
        assert resp.status_code == 303

    rows = (await db.execute(select(Ticket.ticket_number).order_by(Ticket.ticket_number))).scalars().all()
    assert rows == ["TKT-000001", "TKT-000002", "TKT-000003"]
    assert len(set(rows)) == 3
