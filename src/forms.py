import uuid
from enum import Enum
from typing import Any

TRUTHY = {"1", "on", "true", "yes"}
FALSY = {"0", "off", "false", "no"}


def parse_uuid(value: object) -> uuid.UUID | None:
    if value is None or value == "":
        return None
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def parse_enum[E: Enum](enum_cls: type[E], value: object, default: E | None = None) -> E | None:
    try:
        return enum_cls(str(value))
    except (ValueError, TypeError):
        return default


def parse_bool(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in TRUTHY:
        return True
    if text in FALSY:
        return False
    return None


def form_str(form: Any, key: str, default: str = "") -> str:
    return str(form.get(key, default)).strip()


def form_bool(form: Any, key: str) -> bool:
    return parse_bool(form.get(key)) is True


def form_int(form: Any, key: str, default: int = 0) -> int:
    try:
        return int(str(form.get(key, default)))
    except (ValueError, TypeError):
        return default
