import pytest

from src.auth.exceptions import NotAuthenticated, OAuthFailed, UserDeactivated
from src.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    PayloadTooLargeError,
    UnprocessableError,
)
from src.kb.exceptions import (
    ArticleForbidden,
    ArticleNotFound,
    CategoryHasArticles,
    DuplicateSlug,
    InvalidStatusTransition,
    KbNotFound,
)
from src.tickets.exceptions import CategoryHasTickets, CategoryNotFound, InvalidTransition, TicketForbidden, TicketNotFound
from src.users.exceptions import CannotDeactivateLastAdminError, UserNotFoundError


def test_global_exceptions() -> None:
    assert NotFoundError().status_code == 404
    assert ForbiddenError().status_code == 403
    assert BadRequestError().status_code == 400
    assert ConflictError().status_code == 409
    assert PayloadTooLargeError().status_code == 413
    assert UnprocessableError().status_code == 422


def test_auth_exceptions() -> None:
    assert NotAuthenticated().status_code == 401
    assert UserDeactivated().status_code == 403
    assert OAuthFailed().status_code == 400


def test_domain_exceptions() -> None:
    assert KbNotFound().status_code == 404
    assert isinstance(CategoryHasArticles(), ConflictError)
    assert isinstance(DuplicateSlug(), ConflictError)
    assert ArticleNotFound().status_code == 404
    assert isinstance(InvalidStatusTransition(), BadRequestError)
    assert isinstance(ArticleForbidden(), ForbiddenError)
    assert TicketNotFound().status_code == 404
    assert CategoryNotFound().status_code == 404
    assert isinstance(CategoryHasTickets(), ConflictError)
    assert isinstance(InvalidTransition(), BadRequestError)
    assert isinstance(TicketForbidden(), ForbiddenError)
    assert UserNotFoundError().status_code == 404
    assert isinstance(CannotDeactivateLastAdminError(), BadRequestError)


def test_config_normalizes_database_urls() -> None:
    from src.config import Settings

    assert Settings(DATABASE_URL="postgres://u:p@h/db").DATABASE_URL.startswith("postgresql+asyncpg://")
    assert Settings(DATABASE_URL="postgresql://u:p@h/db").DATABASE_URL.startswith("postgresql+asyncpg://")

    relative = Settings(DATABASE_URL="sqlite+aiosqlite:///./instance/x.db")
    assert relative.is_sqlite is True
    assert relative.sqlite_path is not None
    assert relative.sqlite_path.is_absolute()

    absolute = Settings(DATABASE_URL="sqlite+aiosqlite:////tmp/x.db")
    assert absolute.sqlite_path is not None

    postgres = Settings(DATABASE_URL="postgresql+asyncpg://u:p@h/db")
    assert postgres.is_sqlite is False
    assert postgres.sqlite_path is None

    prod = Settings(ENVIRONMENT="production")
    assert prod.is_production is True


def test_dashboard_utils() -> None:
    from src.dashboard import utils

    assert utils.utc_day_start().hour == 0
    assert utils.utc_month_start().day == 1
    assert utils.utc_week_start().weekday() == 0


def test_business_hours_edge_cases() -> None:
    from datetime import UTC, datetime

    from src.tickets.utils import business_hours_add

    before_open = datetime(2026, 1, 5, 6, 0, tzinfo=UTC)
    assert business_hours_add(before_open, 2) == datetime(2026, 1, 5, 11, 0, tzinfo=UTC)

    after_close = datetime(2026, 1, 5, 18, 0, tzinfo=UTC)
    assert business_hours_add(after_close, 2) == datetime(2026, 1, 6, 11, 0, tzinfo=UTC)

    assert business_hours_add(before_open, 0) == before_open


def test_search_scoring() -> None:
    from src.search.service import _score

    assert _score("refund", "Refund") == 5
    assert _score("ref", "Refund") == 4
    assert _score("fund", "Refund") == 3
    assert _score("secret", "Refund", "body secret") == 2
    assert _score("nothing", "Refund", "body") == 1


def test_pagination_defaults() -> None:
    from src.pagination import paginate

    page = paginate(0, 25, 100)
    assert page["page"] == 1
    assert page["total_pages"] == 4


def test_kb_plain_excerpt() -> None:
    from src.kb.markdown import plain_excerpt

    assert plain_excerpt(None) == ""
    assert "bold" in plain_excerpt("**bold** text")


def test_templating_helpers() -> None:
    from src.templating import _markdown_filter, highlight, t

    assert t("does.not.exist") == "does.not.exist"
    assert "x" in str(highlight("x", None))
    assert "&lt;script&gt;" in str(highlight("<script>", None))
    assert "<strong>" in str(_markdown_filter("**b**"))


@pytest.mark.asyncio
async def test_notifications_service_functions(db) -> None:
    from src.auth import service as auth_service
    from src.notifications import service as notification_service

    user = await auth_service.dev_login(db, "notify@example.com")
    await notification_service.create_notification(db, user_id=user.id, type="test", title="Hello", body="Body", link="/x")
    await db.commit()

    assert await notification_service.count_notifications(db, user.id) == 1
    assert await notification_service.count_unread(db, user.id) == 1
    listed = await notification_service.list_notifications(db, user.id, unread_only=True)
    assert len(listed) == 1

    page = await notification_service.list_notifications_page(db, user.id, offset=0, limit=10)
    assert len(page) == 1

    notification = await notification_service.get_notification(db, listed[0].id, user.id)
    assert notification is not None
    assert await notification_service.mark_read(db, notification.id, user.id) is True
    assert await notification_service.count_unread(db, user.id) == 0

    await notification_service.create_notification(db, user_id=user.id, type="test", title="Two")
    await db.commit()
    updated = await notification_service.mark_read_many(db, user.id, [])
    assert updated == 0

    unread_ids = [n.id for n in await notification_service.list_notifications(db, user.id, unread_only=True)]
    assert await notification_service.mark_read_many(db, user.id, unread_ids) == 1
