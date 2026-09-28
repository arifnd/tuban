from src.exceptions import BadRequestError, ConflictError, NotFoundError


class KbNotFound(NotFoundError):
    def __init__(self, detail: str = "Not found") -> None:
        super().__init__(detail=detail)


class CategoryHasArticles(ConflictError):
    def __init__(self) -> None:
        super().__init__(detail="Reassign or delete the category's articles first")


class ArticleNotFound(KbNotFound):
    def __init__(self) -> None:
        super().__init__(detail="Article not found")


class InvalidStatusTransition(BadRequestError):
    def __init__(self, detail: str = "Invalid status transition") -> None:
        super().__init__(detail=detail)
