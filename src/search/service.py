from sqlalchemy.ext.asyncio import AsyncSession

from src.kb import markdown as markdown_utils
from src.kb import service as kb_service
from src.tickets import service as tickets_service
from src.users.models import User

MIN_QUERY_LENGTH = 2
MAX_QUERY_LENGTH = 100


def _score(query: str, title: str, *extra: str) -> int:
    q = query.lower()
    title_lower = (title or "").lower()
    if title_lower == q:
        return 5
    if title_lower.startswith(q):
        return 4
    if q in title_lower:
        return 3
    for field in extra:
        if field and q in field.lower():
            return 2
    return 1


async def search(db: AsyncSession, user: User, query: str, *, limit: int = 20) -> dict:
    query = (query or "").strip()[:MAX_QUERY_LENGTH]
    if len(query) < MIN_QUERY_LENGTH:
        return {"query": query, "hits": [], "kb": [], "tickets": [], "total": 0}

    articles, _ = await kb_service.search_articles(db, user, query, page=1, per_page=limit)
    tickets, _ = await tickets_service.list_tickets(db, user, q=query, page=1, per_page=limit)

    hits: list[dict] = []
    for article in articles:
        hits.append(
            {
                "kind": "kb",
                "id": str(article.id),
                "title": article.title,
                "snippet": markdown_utils.plain_excerpt(article.summary or article.body),
                "url": f"/kb/articles/{article.slug}",
                "score": _score(query, article.title, article.summary or "", article.body or ""),
            }
        )
    for ticket in tickets:
        hits.append(
            {
                "kind": "ticket",
                "id": str(ticket.id),
                "title": f"{ticket.ticket_number} · {ticket.subject}",
                "snippet": (ticket.description or "")[:200],
                "url": f"/tickets/{ticket.id}",
                "score": _score(query, ticket.subject, ticket.description or "", ticket.ticket_number),
            }
        )

    hits.sort(key=lambda hit: (-hit["score"], hit["title"].lower()))
    return {
        "query": query,
        "hits": hits[:limit],
        "kb": [hit for hit in hits if hit["kind"] == "kb"][:limit],
        "tickets": [hit for hit in hits if hit["kind"] == "ticket"][:limit],
        "total": len(hits),
    }
