import json
import re
from datetime import datetime
from functools import lru_cache
from typing import Any

from fastapi.templating import Jinja2Templates
from markupsafe import Markup, escape
from starlette.requests import Request

from src.config import PROJECT_ROOT, settings
from src.kb.markdown import render_markdown as _render_markdown
from src.settings import service as settings_service
from src.settings import theme as theme_palettes
from src.version import __version__

TEMPLATES_DIR = PROJECT_ROOT / "templates"
I18N_DIR = PROJECT_ROOT / "static" / "i18n"
DEFAULT_LANG = "id"

SOCIAL_PLATFORMS = (
    ("facebook", "Facebook"),
    ("instagram", "Instagram"),
    ("x", "X"),
    ("linkedin", "LinkedIn"),
    ("youtube", "YouTube"),
)


@lru_cache
def _load_translations(lang: str = DEFAULT_LANG) -> dict[str, str]:
    path = I18N_DIR / f"{lang}.json"
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def t(key: str) -> str:
    """Return the localized string for ``key``, falling back to the key itself."""
    if key == "brand.name":
        return settings_service.get("app_name") or settings.APP_NAME
    language = settings_service.get("default_language") or DEFAULT_LANG
    return _load_translations(language).get(key, key)


def _context(request: Request) -> dict[str, Any]:
    current_user = getattr(request.state, "current_user", None)
    theme_color = settings_service.get("theme_color") or theme_palettes.DEFAULT_COLOR
    return {
        "current_user": current_user,
        "csrf": getattr(request.state, "csrf", None),
        "is_admin": bool(getattr(current_user, "role", None) == "admin"),
        "current_year": datetime.now().year,
        "unread_notifications": getattr(request.state, "unread_notifications", 0),
        "app_name": settings_service.get("app_name") or settings.APP_NAME,
        "theme_color": theme_color,
        "brand_shades": theme_palettes.css_variables(theme_color),
        "contact_email": settings_service.get("contact_email") or "",
        "contact_phone": settings_service.get("contact_phone") or "",
        "contact_address": settings_service.get("contact_address") or "",
        "social_links": [
            {"name": name, "label": label, "url": settings_service.get(f"social_{name}")}
            for name, label in SOCIAL_PLATFORMS
            if settings_service.get(f"social_{name}")
        ],
        "app_version": __version__,
    }


templates = Jinja2Templates(directory=str(TEMPLATES_DIR), context_processors=[_context])
templates.env.globals.update(t=t, app_name=settings.APP_NAME)


def _tojson(value: object) -> Markup:
    text = json.dumps(value, ensure_ascii=False)
    text = text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return Markup(text)


def _attrjson(value: object) -> Markup:
    text = json.dumps(value, ensure_ascii=False)
    text = text.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e").replace('"', "&quot;")
    return Markup(text)


templates.env.filters["tojson"] = _tojson
templates.env.filters["attrjson"] = _attrjson


def fmt_datetime(value: Any) -> str:
    if value is None:
        return "—"
    return value.strftime("%Y-%m-%d %H:%M")


templates.env.filters["dtf"] = fmt_datetime


def highlight(text: Any, query: str | None) -> Markup:
    """Escape ``text`` and wrap case-insensitive matches of ``query`` in <mark>."""
    if text is None:
        return Markup("")
    if not query:
        return escape(text)
    pattern = re.compile("(" + re.escape(str(query)) + ")", re.IGNORECASE)
    parts = pattern.split(str(text))
    out = []
    for index, part in enumerate(parts):
        if index % 2 == 1:
            out.append(f"<mark>{escape(part)}</mark>")
        else:
            out.append(str(escape(part)))
    return Markup("".join(out))


templates.env.filters["highlight"] = highlight


def _markdown_filter(text: Any) -> Markup:
    return Markup(_render_markdown(text))


templates.env.filters["md"] = _markdown_filter
