from pydantic import BaseModel


class SearchHit(BaseModel):
    kind: str
    id: str
    title: str
    snippet: str
    url: str
    score: int


class SearchResults(BaseModel):
    query: str
    hits: list[SearchHit]
    kb: list[SearchHit]
    tickets: list[SearchHit]
    total: int
