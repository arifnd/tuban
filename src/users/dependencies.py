from typing import Annotated

from fastapi import Depends

from src.auth.dependencies import CurrentUser
from src.exceptions import ForbiddenError
from src.users.models import User


def require_role(*roles: str):
    def _dependency(user: CurrentUser) -> User:
        if user.role not in roles:
            raise ForbiddenError(detail="Insufficient permissions")
        return user

    return _dependency


AdminUser = Annotated[User, Depends(require_role("admin"))]
AgentUser = Annotated[User, Depends(require_role("admin", "agent"))]
