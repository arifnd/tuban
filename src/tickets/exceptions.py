from src.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError


class TicketNotFound(NotFoundError):
    def __init__(self) -> None:
        super().__init__(detail="Ticket not found")


class CategoryNotFound(NotFoundError):
    def __init__(self) -> None:
        super().__init__(detail="Category not found")


class CategoryHasTickets(ConflictError):
    def __init__(self) -> None:
        super().__init__(detail="Reassign or delete the category's tickets first")


class InvalidTransition(BadRequestError):
    def __init__(self, detail: str = "Invalid status transition") -> None:
        super().__init__(detail=detail)


class TicketForbidden(ForbiddenError):
    def __init__(self, detail: str = "You cannot access this ticket") -> None:
        super().__init__(detail=detail)
