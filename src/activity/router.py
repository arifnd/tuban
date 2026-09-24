import uuid

from fastapi import APIRouter, Request

from src.activity import service as activity_service
from src.auth.dependencies import DbDep
from src.pagination import clamp_per_page, paginate
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
    logs, total = await activity_service.list_activity_logs(
        db, user_id=user_id, entity_type=entity_type or None, action=action or None, page=page, per_page=per_page
    )
    pag = paginate(page, per_page, total)
    return templates.TemplateResponse(
        request,
        "activity/list.html",
        {
            "logs": logs,
            "page": pag["page"],
            "per_page": per_page,
            "total_pages": pag["total_pages"],
            "total": pag["total"],
            "users": await activity_service.filter_users(db),
            "entity_types": await activity_service.entity_types(db),
            "filter_user_id": user_id,
            "filter_entity_type": entity_type,
            "filter_action": action,
        },
    )
