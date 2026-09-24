import uuid

from pydantic import BaseModel, Field

from src.kb.models import KbArticleStatus, KbArticleVisibility


class KbCategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    position: int = 0


class KbArticleIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    summary: str | None = None
    body: str = ""
    category_id: uuid.UUID | None = None
    visibility: KbArticleVisibility = KbArticleVisibility.INTERNAL


class KbArticleStatusIn(BaseModel):
    status: KbArticleStatus
