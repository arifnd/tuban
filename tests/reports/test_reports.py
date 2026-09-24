from datetime import date, timedelta

from httpx2 import AsyncClient

from src.reports import exporters
from src.users.models import UserRole
from tests.tickets.helpers import login, make_ticket, make_user

DATE_RANGE = {"start": (date.today() - timedelta(days=30)).isoformat(), "end": date.today().isoformat()}


async def test_reports_require_agent(client: AsyncClient, db) -> None:
    await make_user(db, "u@example.com")
    await login(client, "u@example.com")
    assert (await client.get("/reports")).status_code == 403


async def test_reports_page_and_partials(client: AsyncClient, db) -> None:
    await make_user(db, "agent@example.com", UserRole.AGENT)
    requester = await make_user(db, "u@example.com")
    await make_ticket(db, requester, subject="Report ticket")
    await login(client, "agent@example.com")

    assert (await client.get("/reports")).status_code == 200
    for key in ("ticket-volume", "status", "priority", "sla", "agents", "kb"):
        resp = await client.get(f"/reports/partials/{key}", params=DATE_RANGE)
        assert resp.status_code == 200
    assert (await client.get("/reports/partials/unknown")).status_code == 400


async def test_report_exports(client: AsyncClient, db) -> None:
    await make_user(db, "agent@example.com", UserRole.AGENT)
    requester = await make_user(db, "u@example.com")
    await make_ticket(db, requester)
    await login(client, "agent@example.com")

    expectations = {
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
    }
    for fmt, content_type in expectations.items():
        resp = await client.get("/reports/export", params={"report": "status", "format": fmt, **DATE_RANGE})
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith(content_type)
        assert "attachment" in resp.headers["content-disposition"]
        assert len(resp.content) > 0

    assert (await client.get("/reports/export", params={"report": "status", "format": "xml"})).status_code == 400


async def test_export_range_guard(client: AsyncClient, db) -> None:
    await make_user(db, "agent@example.com", UserRole.AGENT)
    await login(client, "agent@example.com")
    resp = await client.get("/reports/export", params={"report": "status", "format": "csv", "start": "2000-01-01", "end": "2020-01-01"})
    assert resp.status_code == 400


def test_exporter_builders() -> None:
    columns = ["Name", "Count"]
    rows = [["Open", "3"], ["Closed", "1"]]
    assert b"Open" in exporters.build_csv(columns, rows)
    assert exporters.build_xlsx("Report", columns, rows)[:2] == b"PK"
    assert exporters.build_pdf("Report", "subtitle", columns, rows)[:4] == b"%PDF"
