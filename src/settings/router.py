from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from src.auth.dependencies import DbDep
from src.exceptions import BadRequestError
from src.forms import form_bool, form_str
from src.settings import mailer
from src.settings import service as settings_service
from src.settings import theme as theme_palettes
from src.settings.schemas import SettingsUpdate
from src.storage.config import get_storage_settings
from src.templating import t, templates
from src.users.dependencies import AdminUser

router = APIRouter(prefix="/settings", tags=["settings"])

LANGUAGES = [("en", "English"), ("id", "Bahasa Indonesia")]

# Section ids of the settings page menu, in display order.
SETTINGS_SECTIONS = ("general", "sla", "storage", "registration", "contact", "email", "landing", "social")


def _section(value: str | None) -> str:
    """Return a valid settings section id, falling back to the first one."""
    return value if value in SETTINGS_SECTIONS else SETTINGS_SECTIONS[0]


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
            "storage_backend": get_storage_settings().BACKEND,
            "upload_max_size_mb": round(int(values["upload_max_size"]) / (1024 * 1024)),
            "saved": request.query_params.get("saved") == "1",
            "email_test": request.query_params.get("email_test"),
            "smtp_password_set": bool(settings_service.get_secret("smtp_password")),
            "active_section": _section(request.query_params.get("section")),
        },
    )


@router.post("")
async def update_settings(request: Request, db: DbDep, admin: AdminUser):
    form = await request.form()
    section = _section(form_str(form, "section", ""))

    payload = {
        "app_name": form_str(form, "app_name"),
        "default_language": form_str(form, "default_language", settings_service.DEFAULT_LANGUAGE),
        "theme_color": form_str(form, "theme_color", settings_service.DEFAULT_THEME_COLOR),
        "sla_urgent_hours": form_str(form, "sla_urgent_hours", str(settings_service.DEFAULT_SLA_HOURS["sla_urgent_hours"])),
        "sla_high_hours": form_str(form, "sla_high_hours", str(settings_service.DEFAULT_SLA_HOURS["sla_high_hours"])),
        "sla_normal_hours": form_str(form, "sla_normal_hours", str(settings_service.DEFAULT_SLA_HOURS["sla_normal_hours"])),
        "sla_low_hours": form_str(form, "sla_low_hours", str(settings_service.DEFAULT_SLA_HOURS["sla_low_hours"])),
        "ticket_number_prefix": form_str(form, "ticket_number_prefix", settings_service.DEFAULT_TICKET_NUMBER_PREFIX),
        "upload_max_size_mb": form_str(form, "upload_max_size_mb", "20"),
        "allowed_extensions": [ext.strip().lower().lstrip(".") for ext in form_str(form, "allowed_extensions").split(",") if ext.strip()],
        "open_registration": form_bool(form, "open_registration"),
        "require_approval": form_bool(form, "require_approval"),
        "contact_email": form_str(form, "contact_email"),
        "contact_phone": form_str(form, "contact_phone"),
        "contact_address": form_str(form, "contact_address"),
        "landing_heading": form_str(form, "landing_heading"),
        "landing_subheading": form_str(form, "landing_subheading"),
        "social_facebook": form_str(form, "social_facebook"),
        "social_instagram": form_str(form, "social_instagram"),
        "social_x": form_str(form, "social_x"),
        "social_linkedin": form_str(form, "social_linkedin"),
        "social_youtube": form_str(form, "social_youtube"),
        "smtp_enabled": form_bool(form, "smtp_enabled"),
        "smtp_host": form_str(form, "smtp_host"),
        "smtp_port": form_str(form, "smtp_port", str(settings_service.DEFAULT_SMTP_PORT)),
        "smtp_username": form_str(form, "smtp_username"),
        "smtp_password": form_str(form, "smtp_password"),
        "smtp_use_tls": form_bool(form, "smtp_use_tls"),
        "smtp_use_ssl": form_bool(form, "smtp_use_ssl"),
        "smtp_from_email": form_str(form, "smtp_from_email"),
        "smtp_from_name": form_str(form, "smtp_from_name"),
    }
    try:
        data = SettingsUpdate(**payload)
    except ValidationError as exc:
        raise BadRequestError(detail=exc.errors()[0]["msg"]) from exc

    values = {
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
        "landing_heading": data.landing_heading,
        "landing_subheading": data.landing_subheading,
        "social_facebook": data.social_facebook,
        "social_instagram": data.social_instagram,
        "social_x": data.social_x,
        "social_linkedin": data.social_linkedin,
        "social_youtube": data.social_youtube,
        "smtp_enabled": data.smtp_enabled,
        "smtp_host": data.smtp_host,
        "smtp_port": data.smtp_port,
        "smtp_username": data.smtp_username,
        "smtp_use_tls": data.smtp_use_tls,
        "smtp_use_ssl": data.smtp_use_ssl,
        "smtp_from_email": data.smtp_from_email,
        "smtp_from_name": data.smtp_from_name,
    }
    # An empty password field means "keep the currently saved secret".
    if data.smtp_password:
        values["smtp_password"] = data.smtp_password

    await settings_service.update(db, admin, values)
    return RedirectResponse(f"/settings?saved=1&section={section}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/test-email")
async def send_test_email(request: Request, db: DbDep, admin: AdminUser):
    form = await request.form()
    recipient = form_str(form, "smtp_test_to") or admin.email
    try:
        await mailer.send_email(
            to=recipient,
            subject=t("settings.smtp_test_subject"),
            body=t("settings.smtp_test_body"),
        )
    except BadRequestError:
        return RedirectResponse("/settings?email_test=failed&section=email", status_code=status.HTTP_303_SEE_OTHER)
    return RedirectResponse("/settings?email_test=sent&section=email", status_code=status.HTTP_303_SEE_OTHER)
