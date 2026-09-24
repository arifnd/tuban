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
