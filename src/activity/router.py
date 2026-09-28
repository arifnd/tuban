import uuid

from fastapi import APIRouter, Request

from src.activity import service as activity_service
from src.auth.dependencies import DbDep
from src.pagination import Page, clamp_per_page, paginate
from src.templating import templates
from src.users.dependencies import AdminUser

router = APIRouter(prefix="/activity", tags=["activity"])

ACTIVITY_PER_PAGE = 10


@router.get("")
async def activity_page(
    request: Request,
    db: DbDep,
    _: AdminUser,
    page: int = 1,
    per_page: int = ACTIVITY_PER_PAGE,
    user_id: uuid.UUID | None = None,
    entity_type: str = "",
    action: str = "",
):
    per_page = clamp_per_page(per_page)
    total = await activity_service.count_activity_logs(db, user_id=user_id, entity_type=entity_type or None, action=action or None)
    pag = paginate(page, per_page, total)
    logs = await activity_service.list_activity_logs(
        db,
        user_id=user_id,
        entity_type=entity_type or None,
        action=action or None,
        offset=pag["offset"],
        limit=per_page,
    )
    context = Page.create(pag["page"], per_page, logs, total).as_context(
        "logs",
        users=await activity_service.filter_users(db),
        entity_types=await activity_service.entity_types(db),
        filter_user_id=user_id,
        filter_entity_type=entity_type,
        filter_action=action,
    )
    return templates.TemplateResponse(request, "activity/list.html", context)
