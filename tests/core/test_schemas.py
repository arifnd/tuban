from src.auth.schemas import DevLoginIn
from src.dashboard.schemas import ChartSeries
from src.search.schemas import SearchHit, SearchResults


def test_dev_login_schema() -> None:
    assert DevLoginIn(email="a@example.com").email == "a@example.com"


def test_chart_series_schema() -> None:
    series = ChartSeries(labels=["a"], values=[1.0])
    assert series.values == [1.0]


def test_search_schemas() -> None:
    hit = SearchHit(kind="kb", id="1", title="T", snippet="s", url="/x", score=1)
    results = SearchResults(query="q", hits=[hit], kb=[hit], tickets=[], total=1)
    assert results.total == 1
