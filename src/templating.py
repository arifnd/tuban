import json
from datetime import datetime
from functools import lru_cache
from typing import Any

from fastapi.templating import Jinja2Templates
from markupsafe import Markup
from starlette.requests import Request

from src.config import PROJECT_ROOT, settings

TEMPLATES_DIR = PROJECT_ROOT / "templates"
I18N_DIR = PROJECT_ROOT / "static" / "i18n"
DEFAULT_LANG = "en"


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
    return _load_translations(DEFAULT_LANG).get(key, key)


def _context(request: Request) -> dict[str, Any]:
    current_user = getattr(request.state, "current_user", None)
    return {
        "current_user": current_user,
        "csrf": getattr(request.state, "csrf", None),
        "is_admin": bool(getattr(current_user, "role", None) == "admin"),
        "current_year": datetime.now().year,
        "unread_notifications": getattr(request.state, "unread_notifications", 0),
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
