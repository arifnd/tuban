import uuid

from src.auth.schemas import DevLoginIn
from src.dashboard.schemas import ChartSeries
from src.kb.schemas import KbArticleIn, KbArticleStatusIn, KbCategoryIn
from src.reports.schemas import ReportTable
from src.search.schemas import SearchHit, SearchResults
from src.tickets.schemas import CommentCreate, TicketCategoryIn, TicketCreate, TicketFilter, TicketOut
from src.users.schemas import ProfileUpdate, UserActiveUpdate, UserOut, UserRoleUpdate


def test_kb_schemas() -> None:
    assert KbCategoryIn(name="Billing").position == 0
    assert KbArticleIn(title="Hello").visibility.value == "internal"
    assert KbArticleStatusIn(status="published").status.value == "published"


def test_ticket_schemas() -> None:
    assert TicketCategoryIn(name="Billing").name == "Billing"
    created = TicketCreate(subject="Cannot log in")
    assert created.priority.value == "normal"
    assert TicketFilter().sort == "updated"
    assert CommentCreate(body="hi").is_internal is False
    out = TicketOut(id=uuid.uuid4(), ticket_number="TKT-000001", subject="s", status="open", priority="normal", source="web")
    assert out.ticket_number == "TKT-000001"


def test_user_schemas() -> None:
    user = UserOut(id=uuid.uuid4(), email="a@example.com", name="A", role="user", is_active=True)
    assert user.email == "a@example.com"
    assert UserRoleUpdate(role="agent").role.value == "agent"
    assert UserActiveUpdate(is_active=False).is_active is False
    assert ProfileUpdate(name="New").name == "New"


def test_other_schemas() -> None:
    assert DevLoginIn(email="a@example.com").email == "a@example.com"
    series = ChartSeries(labels=["a"], values=[1.0])
    assert series.values == [1.0]
    table = ReportTable(key="status", title="Status", columns=["A"], rows=[["1"]])
    assert table.rows == [["1"]]
    hit = SearchHit(kind="kb", id="1", title="T", snippet="s", url="/x", score=1)
    results = SearchResults(query="q", hits=[hit], kb=[hit], tickets=[], total=1)
    assert results.total == 1
