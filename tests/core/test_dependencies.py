import uuid
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from starlette.requests import Request

from src.auth.config import auth_settings
from src.auth.dependencies import csrf_guard, get_current_user, optional_user
from src.auth.exceptions import NotAuthenticated
from src.auth.utils import create_session_token
from src.exceptions import ForbiddenError
from src.users.dependencies import require_role
from src.users.models import User, UserRole


def _request(headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "scheme": "http",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "root_path": "",
            "headers": headers or [],
            "client": ("127.0.0.1", 1),
            "server": ("test", 80),
        }
    )


def test_require_role() -> None:
    deny = require_role("admin")
    regular = User(email="a@example.com", name="A", role=UserRole.USER)
    with pytest.raises(ForbiddenError):
        deny(regular)

    allow = require_role("admin", "agent")
    agent = User(email="a@example.com", name="A", role=UserRole.AGENT)
    assert allow(agent) is agent


async def test_get_current_user_rejects_malformed_sub(db) -> None:
    payload = {"sub": "not-a-uuid", "csrf": "x", "iat": datetime.now(UTC), "exp": datetime.now(UTC) + timedelta(minutes=5)}
    token = jwt.encode(payload, auth_settings.SESSION_SECRET, algorithm="HS256")
    request = _request([(b"cookie", f"app_session={token}".encode())])
    with pytest.raises(NotAuthenticated):
        await get_current_user(request, db)


async def test_get_current_user_rejects_unknown_user(db) -> None:
    request = _request([(b"cookie", f"app_session={create_session_token(uuid.uuid4())}".encode())])
    with pytest.raises(NotAuthenticated):
        await get_current_user(request, db)


async def test_optional_user_returns_none(db) -> None:
    assert await optional_user(_request(), db) is None


async def test_csrf_guard_paths() -> None:
    ok = _request([(b"x-csrf-token", b"tok")])
    ok.state.csrf = "tok"
    assert await csrf_guard(ok) is None

    mismatch = _request([(b"x-csrf-token", b"bad")])
    mismatch.state.csrf = "tok"
    with pytest.raises(ForbiddenError):
        await csrf_guard(mismatch)

    missing = _request([(b"content-type", b"application/json")])
    missing.state.csrf = "tok"
    with pytest.raises(ForbiddenError):
        await csrf_guard(missing)

    anonymous = _request()
    assert await csrf_guard(anonymous) is None
