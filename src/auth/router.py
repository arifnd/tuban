import secrets
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from src.auth import service as auth_service
from src.auth.config import get_auth_settings
from src.auth.constants import (
    GENERIC_LOGIN_ERROR,
    LOGIN_URL,
    OAUTH_STATE_COOKIE_NAME,
    OAUTH_STATE_MAX_AGE,
    OAUTH_VERIFIER_COOKIE_NAME,
)
from src.auth.dependencies import DbDep, OptionalUser
from src.auth.exceptions import OAuthFailed, UserDeactivated
from src.auth.schemas import DevLoginIn
from src.auth.utils import (
    GOOGLE_AUTHORIZE_URL,
    clear_session_cookie,
    create_oauth_client,
    create_session_token,
    set_session_cookie,
)
from src.ratelimit import rate_limiter
from src.templating import templates
from src.users import service as users_service
from src.users.exceptions import RegistrationClosedError

router = APIRouter(prefix="/auth", tags=["auth"])

FORM_CONTENT_TYPE = "application/x-www-form-urlencoded"


def _home_url() -> str:
    return "/dashboard"


@router.get("/login")
async def login(request: Request, user: OptionalUser):
    if user is not None:
        return RedirectResponse(_home_url(), status_code=status.HTTP_303_SEE_OTHER)
    if request.query_params.get("google"):
        verifier = secrets.token_urlsafe(64)
        client = create_oauth_client()
        authorize_url, state = client.create_authorization_url(GOOGLE_AUTHORIZE_URL, code_verifier=verifier)
        response = RedirectResponse(authorize_url, status_code=status.HTTP_303_SEE_OTHER)
        secure = get_auth_settings().SECURE_COOKIES
        for name, value in ((OAUTH_STATE_COOKIE_NAME, state), (OAUTH_VERIFIER_COOKIE_NAME, verifier)):
            response.set_cookie(name, value, max_age=OAUTH_STATE_MAX_AGE, httponly=True, samesite="lax", secure=secure, path="/")
        return response
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "dev_login_enabled": get_auth_settings().dev_login_enabled,
            "error": request.query_params.get("error"),
        },
    )


@router.get("/callback")
async def callback(request: Request, db: DbDep):
    code = request.query_params.get("code")
    expected_state = request.cookies.get(OAUTH_STATE_COOKIE_NAME)
    verifier = request.cookies.get(OAUTH_VERIFIER_COOKIE_NAME)
    if not code or not expected_state or not verifier:
        response = RedirectResponse(f"{LOGIN_URL}?error={quote(GENERIC_LOGIN_ERROR)}", status_code=status.HTTP_303_SEE_OTHER)
    else:
        try:
            user = await auth_service.login_google(
                db,
                authorization_response=str(request.url),
                expected_state=expected_state,
                code_verifier=verifier,
            )
        except UserDeactivated:
            # A pending registration still needs to be persisted even though the
            # login is refused; the message stays generic to avoid enumeration.
            await db.commit()
            response = RedirectResponse(f"{LOGIN_URL}?error={quote(GENERIC_LOGIN_ERROR)}", status_code=status.HTTP_303_SEE_OTHER)
        except (OAuthFailed, RegistrationClosedError):
            response = RedirectResponse(f"{LOGIN_URL}?error={quote(GENERIC_LOGIN_ERROR)}", status_code=status.HTTP_303_SEE_OTHER)
        else:
            response = RedirectResponse(_home_url(), status_code=status.HTTP_303_SEE_OTHER)
            set_session_cookie(response, create_session_token(user.id))
    # Always drop the short-lived flow cookies, success or failure.
    response.delete_cookie(OAUTH_STATE_COOKIE_NAME, path="/")
    response.delete_cookie(OAUTH_VERIFIER_COOKIE_NAME, path="/")
    return response


@router.post("/dev-login")
async def dev_login(request: Request, db: DbDep):
    if not get_auth_settings().dev_login_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    content_type = request.headers.get("content-type", "").split(";")[0].lower()
    if content_type == FORM_CONTENT_TYPE:
        form = await request.form()
        raw_email = str(form.get("email", "")).strip()
    else:
        raw_email = str((await request.json()).get("email", "")).strip()
    email_key = f"auth:email:{raw_email.lower()}" if raw_email else ""
    if email_key:
        retry_after = rate_limiter.retry_after(email_key)
        if retry_after:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many login attempts",
                headers={"Retry-After": str(retry_after)},
            )
    try:
        email = DevLoginIn(email=raw_email).email
    except ValidationError:
        if email_key:
            rate_limiter.record_failure(email_key)
        if content_type == FORM_CONTENT_TYPE:
            return RedirectResponse(
                f"{LOGIN_URL}?error={quote('Enter a valid email address')}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid email address",
        ) from None
    try:
        user = await auth_service.dev_login(db, email)
    except UserDeactivated:
        # Persist a newly-created (pending-approval) account before refusing login.
        await db.commit()
        raise
    if email_key:
        rate_limiter.reset(email_key)
    response = RedirectResponse(_home_url(), status_code=status.HTTP_303_SEE_OTHER)
    set_session_cookie(response, create_session_token(user.id))
    return response


@router.post("/logout")
async def logout(request: Request, db: DbDep, user: OptionalUser):
    if user is not None:
        users_service.invalidate_sessions(user)
    response = RedirectResponse(LOGIN_URL, status_code=status.HTTP_303_SEE_OTHER)
    clear_session_cookie(response)
    return response
