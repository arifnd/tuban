from typing import Annotated

from fastapi import Depends

from src.users.dependencies import require_role
from src.users.models import User

KbEditor = Annotated[User, Depends(require_role("admin", "agent"))]
