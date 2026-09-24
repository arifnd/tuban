from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from pydantic import ValidationError

from src.auth import service as auth_service
from src.auth.config import auth_settings
from src.auth.constants import LOGIN_URL, OAUTH_STATE_COOKIE_NAME, OAUTH_STATE_MAX_AGE
from src.auth.dependencies import CsrfDep, DbDep, OptionalUser
from src.auth.exceptions import OAuthFailed, UserDeactivated
from src.auth.schemas import DevLoginIn
from src.auth.utils import (
    GOOGLE_AUTHORIZE_URL,
    clear_session_cookie,
    create_oauth_client,
    create_session_token,
    set_session_cookie,
)
from src.templating import templates
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
        client = create_oauth_client()
        authorize_url, state = client.create_authorization_url(GOOGLE_AUTHORIZE_URL)
        response = RedirectResponse(authorize_url, status_code=status.HTTP_303_SEE_OTHER)
        response.set_cookie(
            OAUTH_STATE_COOKIE_NAME,
            state,
            max_age=OAUTH_STATE_MAX_AGE,
            httponly=True,
            samesite="lax",
            secure=auth_settings.SECURE_COOKIES,
            path="/",
        )
        return response
    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "dev_login_enabled": auth_settings.dev_login_enabled,
            "error": request.query_params.get("error"),
        },
    )


@router.get("/callback")
async def callback(request: Request, db: DbDep):
    code = request.query_params.get("code")
    expected_state = request.cookies.get(OAUTH_STATE_COOKIE_NAME)
    if not code or not expected_state:
        return RedirectResponse(
            f"{LOGIN_URL}?error={quote('Sign-in could not be completed')}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    try:
        user = await auth_service.login_google(
            db,
            authorization_response=str(request.url),
            expected_state=expected_state,
        )
    except (OAuthFailed, UserDeactivated, RegistrationClosedError) as exc:
        return RedirectResponse(
            f"{LOGIN_URL}?error={quote(str(exc.detail))}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    response = RedirectResponse(_home_url(), status_code=status.HTTP_303_SEE_OTHER)
    set_session_cookie(response, create_session_token(user.id))
    response.delete_cookie(OAUTH_STATE_COOKIE_NAME, path="/")
    return response


@router.post("/dev-login")
async def dev_login(request: Request, db: DbDep):
    if not auth_settings.dev_login_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    content_type = request.headers.get("content-type", "").split(";")[0].lower()
    if content_type == FORM_CONTENT_TYPE:
        form = await request.form()
        raw_email = str(form.get("email", "")).strip()
    else:
        raw_email = str((await request.json()).get("email", "")).strip()
    try:
        email = DevLoginIn(email=raw_email).email
    except ValidationError:
        if content_type == FORM_CONTENT_TYPE:
            return RedirectResponse(
                f"{LOGIN_URL}?error={quote('Enter a valid email address')}",
                status_code=status.HTTP_303_SEE_OTHER,
            )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid email address",
        ) from None
    user = await auth_service.dev_login(db, email)
    response = RedirectResponse(_home_url(), status_code=status.HTTP_303_SEE_OTHER)
    set_session_cookie(response, create_session_token(user.id))
    return response


@router.post("/logout")
async def logout(request: Request, _: CsrfDep):
    response = RedirectResponse(LOGIN_URL, status_code=status.HTTP_303_SEE_OTHER)
    clear_session_cookie(response)
    return response
