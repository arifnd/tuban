from src.exceptions import BadRequestError, ForbiddenError, NotFoundError


class UserNotFoundError(NotFoundError):
    def __init__(self) -> None:
        super().__init__(detail="User not found")


class CannotDeactivateLastAdminError(BadRequestError):
    def __init__(self) -> None:
        super().__init__(detail="You cannot deactivate or demote the last active admin")


class RegistrationClosedError(ForbiddenError):
    def __init__(self) -> None:
        super().__init__(detail="Pendaftaran akun ditutup")
