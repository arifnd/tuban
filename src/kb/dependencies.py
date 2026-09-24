import uuid
from typing import Annotated

from fastapi import Depends

from src.auth.dependencies import DbDep
from src.kb import service as kb_service
from src.kb.models import KbCategory
from src.users.dependencies import require_role
from src.users.models import User

KbEditor = Annotated[User, Depends(require_role("admin", "agent"))]


async def _category(db: DbDep, category_id: uuid.UUID) -> KbCategory:
    return await kb_service.get_category_by_id(db, category_id)


KbCategoryDep = Annotated[KbCategory, Depends(_category)]
