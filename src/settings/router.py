from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from src.auth.dependencies import DbDep
from src.exceptions import BadRequestError
from src.forms import form_bool, form_str
from src.settings import service as settings_service
from src.settings import theme as theme_palettes
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
            "brand_colors": theme_palettes.options(),
            "storage_backend": storage_settings.BACKEND,
            "upload_max_size_mb": round(int(values["upload_max_size"]) / (1024 * 1024)),
            "saved": request.query_params.get("saved") == "1",
        },
    )


@router.post("")
async def update_settings(request: Request, db: DbDep, admin: AdminUser):
    form = await request.form()

    payload = {
        "app_name": form_str(form, "app_name"),
        "default_language": form_str(form, "default_language", "id"),
        "theme_color": form_str(form, "theme_color", "green"),
        "sla_urgent_hours": form_str(form, "sla_urgent_hours", "4"),
        "sla_high_hours": form_str(form, "sla_high_hours", "8"),
        "sla_normal_hours": form_str(form, "sla_normal_hours", "24"),
        "sla_low_hours": form_str(form, "sla_low_hours", "72"),
        "ticket_number_prefix": form_str(form, "ticket_number_prefix", "TKT"),
        "upload_max_size_mb": form_str(form, "upload_max_size_mb", "20"),
        "allowed_extensions": [ext.strip().lower().lstrip(".") for ext in form_str(form, "allowed_extensions").split(",") if ext.strip()],
        "open_registration": form_bool(form, "open_registration"),
        "require_approval": form_bool(form, "require_approval"),
        "contact_email": form_str(form, "contact_email"),
        "contact_phone": form_str(form, "contact_phone"),
        "contact_address": form_str(form, "contact_address"),
        "social_facebook": form_str(form, "social_facebook"),
        "social_instagram": form_str(form, "social_instagram"),
        "social_x": form_str(form, "social_x"),
        "social_linkedin": form_str(form, "social_linkedin"),
        "social_youtube": form_str(form, "social_youtube"),
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
            "theme_color": data.theme_color,
            "sla_urgent_hours": data.sla_urgent_hours,
            "sla_high_hours": data.sla_high_hours,
            "sla_normal_hours": data.sla_normal_hours,
            "sla_low_hours": data.sla_low_hours,
            "ticket_number_prefix": data.ticket_number_prefix,
            "upload_max_size": data.upload_max_size_mb * 1024 * 1024,
            "allowed_extensions": data.allowed_extensions,
            "open_registration": data.open_registration,
            "require_approval": data.require_approval,
            "contact_email": data.contact_email,
            "contact_phone": data.contact_phone,
            "contact_address": data.contact_address,
            "social_facebook": data.social_facebook,
            "social_instagram": data.social_instagram,
            "social_x": data.social_x,
            "social_linkedin": data.social_linkedin,
            "social_youtube": data.social_youtube,
        },
    )
    return RedirectResponse("/settings?saved=1", status_code=status.HTTP_303_SEE_OTHER)
