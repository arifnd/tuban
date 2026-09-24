from fastapi import HTTPException, status


class NotAuthenticated(HTTPException):
    def __init__(self, detail: str = "Authentication required") -> None:
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class UserDeactivated(HTTPException):
    def __init__(self, detail: str = "This account has been deactivated") -> None:
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class OAuthFailed(HTTPException):
    def __init__(self, detail: str = "Google sign-in failed") -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)
