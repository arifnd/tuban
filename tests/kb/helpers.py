from sqlalchemy import select

from src.kb.models import KbArticle, KbArticleStatus, KbArticleVisibility, KbCategory
from src.users.models import User, UserRole
from tests.helpers import csrf, login, make_user  # noqa: F401  (re-exported for tests)

__all__ = ["csrf", "get_category", "login", "make_article", "make_editor", "make_user"]


async def make_editor(db, email: str) -> User:
    return await make_user(db, email, UserRole.AGENT)


async def make_article(
    db, author: User, *, title="Hello", body="Body", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.PUBLIC, **kwargs
) -> KbArticle:
    article = KbArticle(title=title, slug=title.lower().replace(" ", "-"), body=body, author_id=author.id, status=status, visibility=visibility, **kwargs)
    db.add(article)
    await db.commit()
    await db.refresh(article)
    return article


async def get_category(db, name: str) -> KbCategory:
    return (await db.execute(select(KbCategory).where(KbCategory.name == name))).scalar_one()
