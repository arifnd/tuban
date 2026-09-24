import uuid

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse, RedirectResponse

from src.auth.dependencies import CsrfDep, CurrentUser, DbDep
from src.notifications import service as notification_service
from src.notifications.constants import NOTIFICATIONS_PER_PAGE
from src.pagination import clamp_per_page, paginate
from src.templating import templates

router = APIRouter(prefix="/notifications", tags=["notifications"])


async def _dropdown_context(db, user) -> dict:
    return {
        "notifications": await notification_service.list_notifications(db, user.id, limit=8, unread_only=True),
        "unread_notifications": await notification_service.count_unread(db, user.id),
    }


async def _page_context(db, user, page: int, per_page: int) -> dict:
    pag = paginate(page, per_page, await notification_service.count_notifications(db, user.id))
    return {
        "notifications": await notification_service.list_notifications_page(db, user.id, offset=pag["offset"], limit=per_page),
        "unread_notifications": await notification_service.count_unread(db, user.id),
        "page": pag["page"],
        "per_page": per_page,
        "total_pages": pag["total_pages"],
        "total": pag["total"],
    }


@router.get("")
async def notifications_page(request: Request, db: DbDep, user: CurrentUser, page: int = 1, per_page: int = NOTIFICATIONS_PER_PAGE):
    per_page = clamp_per_page(per_page)
    context = await _page_context(db, user, page, per_page)
    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(request, "partials/notifications/list.html", context)
    return templates.TemplateResponse(request, "notifications/index.html", context)


@router.get("/partial")
async def notifications_partial(request: Request, db: DbDep, user: CurrentUser):
    return templates.TemplateResponse(request, "partials/notifications/dropdown.html", await _dropdown_context(db, user))


@router.get("/api")
async def notifications_api(db: DbDep, user: CurrentUser):
    notifications = await notification_service.list_notifications(db, user.id, limit=10, unread_only=True)
    return JSONResponse(
        {
            "notifications": [
                {
                    "id": str(notification.id),
                    "title": notification.title,
                    "body": notification.body,
                    "link": notification.link,
                    "created_at": notification.created_at.isoformat() if notification.created_at else None,
                    "is_read": notification.is_read,
                }
                for notification in notifications
            ],
            "unread_notifications": await notification_service.count_unread(db, user.id),
        }
    )


async def _hx_response(request: Request, db, user, page: int, per_page: int):
    if request.headers.get("HX-Target") == "notif-dropdown":
        return templates.TemplateResponse(request, "partials/notifications/dropdown.html", await _dropdown_context(db, user))
    return templates.TemplateResponse(request, "partials/notifications/list.html", await _page_context(db, user, page, per_page))


@router.post("/read-many")
async def mark_read_many(request: Request, db: DbDep, user: CurrentUser, _: CsrfDep):
    ids = await _notification_ids(request)
    await notification_service.mark_read_many(db, user.id, ids)
    if request.headers.get("HX-Request") == "true":
        return await _hx_response(request, db, user, 1, NOTIFICATIONS_PER_PAGE)
    return RedirectResponse("/notifications", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/read-all")
async def mark_all_read(request: Request, db: DbDep, user: CurrentUser, _: CsrfDep):
    await notification_service.mark_all_read(db, user.id)
    if request.headers.get("HX-Request") == "true":
        return await _hx_response(request, db, user, 1, NOTIFICATIONS_PER_PAGE)
    return RedirectResponse("/notifications", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/{notification_id}/open")
async def open_notification(db: DbDep, user: CurrentUser, notification_id: uuid.UUID):
    notification = await notification_service.get_notification(db, notification_id, user.id)
    if notification is None:
        return RedirectResponse("/notifications", status_code=status.HTTP_303_SEE_OTHER)
    if not notification.is_read:
        await notification_service.mark_read(db, notification_id, user.id)
    return RedirectResponse(notification.link or "/notifications", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/{notification_id}/read")
async def mark_read(request: Request, db: DbDep, user: CurrentUser, _: CsrfDep, notification_id: uuid.UUID):
    await notification_service.mark_read(db, notification_id, user.id)
    if request.headers.get("HX-Request") == "true":
        return await _hx_response(request, db, user, 1, NOTIFICATIONS_PER_PAGE)
    return RedirectResponse("/notifications", status_code=status.HTTP_303_SEE_OTHER)


async def _notification_ids(request: Request) -> list[uuid.UUID]:
    ids: list[uuid.UUID] = []
    content_type = request.headers.get("content-type", "")
    is_json = content_type.startswith("application/json")
    raw = (await request.json()).get("ids", []) if is_json else (await request.form()).getlist("notification_ids")
    for value in raw:
        try:
            ids.append(uuid.UUID(str(value)))
        except (ValueError, TypeError):
            continue
    return ids
