from typing import Annotated

from fastapi import APIRouter, Query, Request

from src.auth.dependencies import CurrentUser, DbDep
from src.dashboard import service as dashboard_service
from src.dashboard.schemas import ChartSeries
from src.templating import templates
from src.users.models import UserRole

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _is_staff(user) -> bool:
    return user.role in (UserRole.ADMIN, UserRole.AGENT)


async def _summary(db, user) -> dict:
    trend = await dashboard_service.ticket_trend(db)
    return {
        "is_staff": _is_staff(user),
        "stats": await dashboard_service.team_stats(db) if _is_staff(user) else await dashboard_service.user_stats(db, user),
        "kb": await dashboard_service.kb_stats(db),
        "recent_tickets": await dashboard_service.recent_tickets(db, user),
        "activities": await dashboard_service.recent_activity(db, user),
        "trend_labels": trend.labels,
        "trend_values": trend.values,
    }


@router.get("")
async def dashboard(request: Request, db: DbDep, user: CurrentUser):
    return templates.TemplateResponse(request, "dashboard/index.html", await _summary(db, user))


@router.get("/partials/stats")
async def stats_partial(request: Request, db: DbDep, user: CurrentUser):
    return templates.TemplateResponse(request, "partials/dashboard/stats.html", await _summary(db, user))


@router.get("/partials/activity")
async def activity_partial(request: Request, db: DbDep, user: CurrentUser):
    return templates.TemplateResponse(
        request,
        "partials/dashboard/activity.html",
        {
            "activities": await dashboard_service.recent_activity(db, user),
            "recent_tickets": await dashboard_service.recent_tickets(db, user),
        },
    )


@router.get("/api/ticket-trend", response_model=ChartSeries)
async def ticket_trend(
    db: DbDep,
    user: CurrentUser,
    days: Annotated[int, Query(ge=7, le=90)] = 14,
) -> ChartSeries:
    return await dashboard_service.ticket_trend(db, days)
