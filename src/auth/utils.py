import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from authlib.integrations.httpx_client import AsyncOAuth2Client
from jwt.exceptions import InvalidTokenError
from starlette.responses import Response

from src.auth.config import auth_settings
from src.auth.constants import SESSION_COOKIE_NAME

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_SCOPE = "openid email profile"

SESSION_ALG = "HS256"


def create_oauth_client(token: dict | None = None) -> AsyncOAuth2Client:
    return AsyncOAuth2Client(
        client_id=auth_settings.GOOGLE_CLIENT_ID,
        client_secret=auth_settings.GOOGLE_CLIENT_SECRET,
        redirect_uri=auth_settings.GOOGLE_REDIRECT_URI,
        scope=GOOGLE_SCOPE,
        authorization_endpoint=GOOGLE_AUTHORIZE_URL,
        token_endpoint=GOOGLE_TOKEN_URL,
        token=token,
    )


async def fetch_google_profile(token: dict) -> dict:
    client = create_oauth_client(token=token)
    resp = await client.get(GOOGLE_USERINFO_URL)
    resp.raise_for_status()
    profile = resp.json()
    if not profile.get("email") or not profile.get("email_verified"):
        raise InvalidTokenError("Google profile has no verified email")
    return profile


def create_session_token(user_id: uuid.UUID) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "csrf": secrets.token_hex(16),
        "iat": now,
        "exp": now + timedelta(minutes=auth_settings.SESSION_EXP_MINUTES),
    }
    return jwt.encode(payload, auth_settings.SESSION_SECRET, algorithm=SESSION_ALG)


def decode_session_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, auth_settings.SESSION_SECRET, algorithms=[SESSION_ALG])
    except InvalidTokenError:
        return None


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE_NAME,
        token,
        max_age=auth_settings.SESSION_EXP_MINUTES * 60,
        httponly=True,
        samesite="lax",
        secure=auth_settings.SECURE_COOKIES,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE_NAME, path="/")
