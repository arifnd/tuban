from dataclasses import dataclass
from typing import Any

MAX_PER_PAGE = 100


def clamp_per_page(per_page: int, *, maximum: int = MAX_PER_PAGE) -> int:
    return max(1, min(per_page, maximum))


def paginate(page: int, per_page: int, total: int) -> dict:
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = min(max(page, 1), total_pages)
    return {
        "page": page,
        "per_page": per_page,
        "offset": (page - 1) * per_page,
        "total": total,
        "total_pages": total_pages,
    }


@dataclass(frozen=True)
class Page[T]:
    """A resolved page of results plus the context keys templates expect."""

    items: list[T]
    page: int
    per_page: int
    total: int
    total_pages: int
    offset: int

    @classmethod
    def create(cls, page: int, per_page: int, items: list[T], total: int) -> "Page[T]":
        resolved = paginate(page, per_page, total)
        return cls(
            items=list(items),
            page=resolved["page"],
            per_page=resolved["per_page"],
            total=resolved["total"],
            total_pages=resolved["total_pages"],
            offset=resolved["offset"],
        )

    def as_context(self, items_key: str, **extra: Any) -> dict[str, Any]:
        context: dict[str, Any] = {
            items_key: self.items,
            "page": self.page,
            "per_page": self.per_page,
            "total": self.total,
            "total_pages": self.total_pages,
        }
        context.update(extra)
        return context
