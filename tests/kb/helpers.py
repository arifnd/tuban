from httpx2 import AsyncClient
from sqlalchemy import select

from src.auth import service as auth_service
from src.auth.utils import decode_session_token
from src.kb.models import KbArticle, KbArticleStatus, KbArticleVisibility, KbCategory
from src.users.models import User, UserRole


def csrf(cookies) -> str:
    return decode_session_token(cookies["app_session"])["csrf"]


async def login(client: AsyncClient, email: str) -> None:
    client.cookies.clear()
    resp = await client.post("/auth/dev-login", json={"email": email})
    assert resp.status_code == 303


async def make_editor(db, email: str) -> User:
    user = await auth_service.dev_login(db, email)
    user.role = UserRole.AGENT
    await db.commit()
    await db.refresh(user)
    return user


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
