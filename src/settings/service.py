from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.activity import service as activity_service
from src.config import settings as config_settings
from src.settings.models import AppSetting
from src.storage.config import storage_settings
from src.storage.constants import ALLOWED_EXTENSIONS


def defaults() -> dict[str, Any]:
    return {
        "app_name": config_settings.APP_NAME,
        "default_language": "id",
        "theme_color": "green",
        "initial_admin_email": config_settings.INITIAL_ADMIN_EMAIL,
        "sla_urgent_hours": 4,
        "sla_high_hours": 8,
        "sla_normal_hours": 24,
        "sla_low_hours": 72,
        "ticket_number_prefix": "TKT",
        "upload_max_size": storage_settings.UPLOAD_MAX_SIZE,
        "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
        "open_registration": True,
        "require_approval": False,
        "contact_email": "",
        "contact_phone": "",
        "contact_address": "",
        "social_facebook": "",
        "social_instagram": "",
        "social_x": "",
        "social_linkedin": "",
        "social_youtube": "",
        "carousel_slides": [],
    }


_cache: dict[str, Any] | None = None


def reset_cache() -> None:
    global _cache
    _cache = None


async def load(db: AsyncSession) -> dict[str, Any]:
    global _cache
    cache = defaults()
    for row in (await db.execute(select(AppSetting))).scalars():
        cache[row.key] = row.value
    _cache = cache
    return cache


def all() -> dict[str, Any]:
    merged = defaults()
    if _cache is not None:
        merged.update(_cache)
    return merged


def get(key: str) -> Any:
    base = defaults()
    if _cache is None or key not in _cache:
        return base.get(key)
    return _cache[key]


def carousel_slides() -> list[dict[str, str]]:
    slides = get("carousel_slides") or []
    if not isinstance(slides, list):
        return []
    cleaned = []
    for slide in slides:
        if not isinstance(slide, dict) or not slide.get("image"):
            continue
        cleaned.append(
            {
                "image": str(slide.get("image", "")),
                "title": str(slide.get("title", "")),
                "subtitle": str(slide.get("subtitle", "")),
            }
        )
    return cleaned


async def update(db: AsyncSession, actor, values: dict[str, Any]) -> dict[str, Any]:
    known = defaults()
    for key, value in values.items():
        if key not in known:
            continue
        row = await db.get(AppSetting, key)
        if row is None:
            db.add(AppSetting(key=key, value=value))
        else:
            row.value = value
    await activity_service.log(db, user_id=actor.id, action="update", entity_type="app_settings", new_data=values)
    await db.commit()
    return await load(db)
