import secrets
from urllib.parse import parse_qsl

from starlette.datastructures import Headers
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from src.auth.constants import CSRF_FORM_FIELD, CSRF_HEADER, SESSION_COOKIE_NAME
from src.auth.utils import decode_session_token
from src.config import settings
from src.storage import service as storage_service

SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
FORM_URLENCODED = "application/x-www-form-urlencoded"
MULTIPART = "multipart/form-data"

# Allowance for multipart boundaries and non-file form fields on top of the
# configured per-file upload limit.
REQUEST_SIZE_OVERHEAD = 64 * 1024

CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://unpkg.com https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: https:; "
    "font-src 'self' data:; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)


class _RequestBodyTooLarge(Exception):
    pass


class BodySizeLimitMiddleware:
    """Reject unsafe request bodies while they stream in.

    ``Content-Length`` is advisory: a chunked request or a falsified length can
    otherwise smuggle an unbounded body past the app. This middleware wraps the
    ASGI ``receive`` callable and aborts the moment the accumulated body exceeds
    the runtime-configured upload limit (plus multipart overhead).
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] in SAFE_METHODS:
            await self.app(scope, receive, send)
            return

        limit = storage_service.max_upload_size() + REQUEST_SIZE_OVERHEAD
        raw_length = Headers(scope=scope).get("content-length")
        if raw_length is not None:
            try:
                if int(raw_length) > limit:
                    await PlainTextResponse("Request body too large", status_code=413)(scope, receive, send)
                    return
            except ValueError:
                pass

        received = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise _RequestBodyTooLarge
            return message

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracking_send)
        except _RequestBodyTooLarge:
            if not response_started:
                await PlainTextResponse("Request body too large", status_code=413)(scope, receive, send)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        self._load_session(request)
        response = await self._check_csrf(request)
        if response is None:
            response = await call_next(request)
        self._apply_headers(response)
        return response

    def _load_session(self, request: Request) -> None:
        token = request.cookies.get(SESSION_COOKIE_NAME)
        payload = decode_session_token(token) if token else None
        request.state.session_payload = payload
        if payload:
            request.state.user_id = payload["sub"]
            request.state.csrf = payload["csrf"]

    async def _check_csrf(self, request: Request) -> Response | None:
        if request.method in SAFE_METHODS:
            return None
        payload = getattr(request.state, "session_payload", None)
        if payload is None:
            return None
        expected = payload["csrf"]
        provided = request.headers.get(CSRF_HEADER)
        content_type = request.headers.get("content-type", "").split(";")[0].lower()
        if not provided:
            if content_type == FORM_URLENCODED:
                body = await request.body()
                provided = dict(parse_qsl(body.decode())).get(CSRF_FORM_FIELD)
            elif content_type == MULTIPART:
                # Cache the raw body so the endpoint can replay it downstream;
                # Request.stream() (used by form parsing) does not cache it.
                await request.body()
                form = await request.form()
                provided = form.get(CSRF_FORM_FIELD)
        if not provided or not secrets.compare_digest(str(provided), str(expected)):
            return PlainTextResponse("CSRF token mismatch", status_code=403)
        return None

    def _apply_headers(self, response: Response) -> None:
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        if settings.is_production:
            response.headers.setdefault("Strict-Transport-Security", "max-age=63072000; includeSubDomains")
