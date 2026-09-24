import uuid
from typing import Annotated

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import RedirectResponse

from src.activity import service as activity_service
from src.auth.dependencies import CsrfDep, CurrentUser, DbDep
from src.exceptions import BadRequestError
from src.pagination import clamp_per_page, paginate
from src.templating import templates
from src.users import service as users_service
from src.users.constants import USERS_PER_PAGE
from src.users.dependencies import AdminUser
from src.users.models import UserRole

router = APIRouter(tags=["users"])


def _parse_role(value: str | None) -> UserRole | None:
    if not value:
        return None
    try:
        return UserRole(value)
    except ValueError:
        return None


def _parse_active(value: str | None) -> bool | None:
    if value == "1":
        return True
    if value == "0":
        return False
    return None


async def _list_context(db, admin, q, role, active, page, per_page) -> dict:
    per_page = clamp_per_page(per_page)
    users, total = await users_service.list_users(
        db,
        search=q or None,
        role=_parse_role(role),
        is_active=_parse_active(active),
        page=page,
        per_page=per_page,
        exclude_id=admin.id,
    )
    pag = paginate(page, per_page, total)
    return {
        "users": users,
        "search": q or "",
        "role_filter": role or "",
        "active_filter": active or "",
        "roles": UserRole,
        "page": pag["page"],
        "per_page": per_page,
        "total_pages": pag["total_pages"],
        "total": pag["total"],
    }


@router.get("/users")
async def list_users(
    request: Request,
    db: DbDep,
    admin: AdminUser,
    q: str = "",
    role: str = "",
    active: str = "",
    page: int = 1,
    per_page: int = USERS_PER_PAGE,
):
    context = await _list_context(db, admin, q, role, active, page, per_page)
    if request.headers.get("HX-Request") == "true":
        return templates.TemplateResponse(request, "users/partials/user_table.html", context)
    return templates.TemplateResponse(request, "users/list.html", context)


@router.get("/users/{user_id}")
async def user_detail(request: Request, db: DbDep, admin: AdminUser, user_id: uuid.UUID):
    user = await users_service.get_user_by_id(db, user_id)
    return templates.TemplateResponse(request, "users/detail.html", {"user": user, "roles": UserRole})


@router.post("/users/{user_id}/role")
async def update_role(
    request: Request,
    db: DbDep,
    admin: AdminUser,
    _: CsrfDep,
    user_id: uuid.UUID,
    role: Annotated[str, Form()],
):
    user = await users_service.get_user_by_id(db, user_id)
    try:
        new_role = UserRole(role)
    except ValueError:
        raise BadRequestError(detail="Invalid role") from None
    old_role = user.role.value
    await users_service.set_user_role(db, user, new_role)
    await activity_service.log(
        db,
        user_id=admin.id,
        action="update",
        entity_type="users",
        entity_id=user.id,
        old_data={"role": old_role},
        new_data={"role": new_role.value},
    )
    await db.commit()
    return RedirectResponse(f"/users/{user.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/users/{user_id}/active")
async def toggle_active(
    request: Request,
    db: DbDep,
    admin: AdminUser,
    _: CsrfDep,
    user_id: uuid.UUID,
):
    user = await users_service.get_user_by_id(db, user_id)
    if user.id == admin.id:
        raise BadRequestError(detail="You cannot deactivate your own account")
    target = not user.is_active
    await users_service.set_user_active(db, user, target)
    await activity_service.log(
        db,
        user_id=admin.id,
        action="update",
        entity_type="users",
        entity_id=user.id,
        new_data={"is_active": target},
    )
    await db.commit()
    return RedirectResponse(f"/users/{user.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/profile")
async def profile_page(request: Request, user: CurrentUser):
    return templates.TemplateResponse(request, "users/profile.html")


@router.post("/profile")
async def profile_update(
    request: Request,
    db: DbDep,
    user: CurrentUser,
    _: CsrfDep,
    name: Annotated[str, Form()] = "",
):
    name = name.strip()
    if not name:
        return templates.TemplateResponse(
            request,
            "users/profile.html",
            {"error": "Name is required"},
            status_code=status.HTTP_400_BAD_REQUEST,
        )
    await users_service.update_profile(db, user, name)
    return RedirectResponse("/profile", status_code=status.HTTP_303_SEE_OTHER)
