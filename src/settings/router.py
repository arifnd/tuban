from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from src.auth.dependencies import CsrfDep, DbDep
from src.exceptions import BadRequestError
from src.settings import service as settings_service
from src.settings.schemas import SettingsUpdate
from src.storage.config import storage_settings
from src.templating import templates
from src.users.dependencies import AdminUser

router = APIRouter(prefix="/settings", tags=["settings"])

LANGUAGES = [("en", "English"), ("id", "Bahasa Indonesia")]


@router.get("")
async def settings_page(request: Request, db: DbDep, _: AdminUser):
    values = settings_service.all()
    return templates.TemplateResponse(
        request,
        "settings/index.html",
        {
            "values": values,
            "languages": LANGUAGES,
            "storage_backend": storage_settings.BACKEND,
            "upload_max_size_mb": round(int(values["upload_max_size"]) / (1024 * 1024)),
        },
    )


@router.post("")
async def update_settings(request: Request, db: DbDep, admin: AdminUser, _: CsrfDep):
    form = await request.form()

    def field(name: str, default: str = "") -> str:
        return str(form.get(name, default)).strip()

    def checked(name: str) -> bool:
        return str(form.get(name, "")) in {"1", "on", "true", "yes"}

    payload = {
        "app_name": field("app_name"),
        "default_language": field("default_language", "id"),
        "sla_urgent_hours": field("sla_urgent_hours", "4"),
        "sla_high_hours": field("sla_high_hours", "8"),
        "sla_normal_hours": field("sla_normal_hours", "24"),
        "sla_low_hours": field("sla_low_hours", "72"),
        "upload_max_size_mb": field("upload_max_size_mb", "20"),
        "allowed_extensions": [ext.strip().lower().lstrip(".") for ext in field("allowed_extensions").split(",") if ext.strip()],
        "open_registration": checked("open_registration"),
        "require_approval": checked("require_approval"),
    }
    try:
        data = SettingsUpdate(**payload)
    except ValidationError as exc:
        raise BadRequestError(detail=exc.errors()[0]["msg"]) from exc

    await settings_service.update(
        db,
        admin,
        {
            "app_name": data.app_name,
            "default_language": data.default_language,
            "sla_urgent_hours": data.sla_urgent_hours,
            "sla_high_hours": data.sla_high_hours,
            "sla_normal_hours": data.sla_normal_hours,
            "sla_low_hours": data.sla_low_hours,
            "upload_max_size": data.upload_max_size_mb * 1024 * 1024,
            "allowed_extensions": data.allowed_extensions,
            "open_registration": data.open_registration,
            "require_approval": data.require_approval,
        },
    )
    return RedirectResponse("/settings", status_code=status.HTTP_303_SEE_OTHER)
