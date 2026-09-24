from authlib.integrations.base_client import OAuthError
from httpx2 import HTTPError
from jwt.exceptions import InvalidTokenError
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth import utils as auth_utils
from src.auth.exceptions import OAuthFailed
from src.users import service as users_service
from src.users.models import User


async def login_google(db: AsyncSession, authorization_response: str, expected_state: str) -> User:
    client = auth_utils.create_oauth_client()
    try:
        token = await client.fetch_token(
            authorization_response=authorization_response,
            state=expected_state,
        )
        profile = await auth_utils.fetch_google_profile(token)
    except (OAuthError, HTTPError, InvalidTokenError, ValueError) as exc:
        raise OAuthFailed() from exc
    return await users_service.ensure_user(
        db,
        google_id=profile.get("sub"),
        email=profile["email"],
        name=profile.get("name") or profile["email"],
        avatar=profile.get("picture"),
    )


async def dev_login(db: AsyncSession, email: str) -> User:
    return await users_service.ensure_user(
        db,
        google_id=None,
        email=email,
        name=email,
    )
