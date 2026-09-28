import uuid
from enum import StrEnum

from src.forms import form_bool, form_int, form_str, parse_bool, parse_enum, parse_uuid


class Color(StrEnum):
    RED = "red"
    BLUE = "blue"


def test_parse_uuid() -> None:
    value = uuid.uuid4()
    assert parse_uuid(value) == value
    assert parse_uuid(str(value)) == value
    assert parse_uuid("") is None
    assert parse_uuid(None) is None
    assert parse_uuid("not-a-uuid") is None


def test_parse_enum() -> None:
    assert parse_enum(Color, "red") is Color.RED
    assert parse_enum(Color, None) is None
    assert parse_enum(Color, "nope") is None
    assert parse_enum(Color, "nope", Color.BLUE) is Color.BLUE


def test_parse_bool() -> None:
    for truthy in ("1", "on", "true", "TRUE", "yes", True, 1):
        assert parse_bool(truthy) is True
    for falsy in ("0", "off", "false", "no", False, 0):
        assert parse_bool(falsy) is False
    assert parse_bool("maybe") is None
    assert parse_bool(None) is None


def test_form_helpers() -> None:
    form = {"name": "  hi  ", "active": "on", "count": "5", "bad": "x"}
    assert form_str(form, "name") == "hi"
    assert form_str(form, "missing", "fallback") == "fallback"
    assert form_bool(form, "active") is True
    assert form_bool(form, "missing") is False
    assert form_int(form, "count") == 5
    assert form_int(form, "bad", 7) == 7
    assert form_int(form, "missing", 3) == 3
