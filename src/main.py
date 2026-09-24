import logging
import logging.config
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.activity import router as activity_router
from src.auth import router as auth_router
from src.auth.dependencies import OptionalUser
from src.auth.exceptions import NotAuthenticated
from src.config import PROJECT_ROOT, settings
from src.dashboard import router as dashboard_router
from src.kb import router as kb_router
from src.middleware import SecurityHeadersMiddleware
from src.notifications import router as notifications_router
from src.storage import router as storage_router
from src.templating import templates
from src.tickets import router as tickets_router
from src.users import router as users_router
from src.version import __version__

logging_file = Path(__file__).resolve().parent.parent / "logging.ini"
if logging_file.exists():
    logging.config.fileConfig(logging_file, disable_existing_loggers=False)

logger = logging.getLogger(__name__)

SHOW_DOCS_IN = {"local", "staging"}
app_kwargs: dict = {"title": settings.APP_NAME, "version": __version__}
if settings.ENVIRONMENT not in SHOW_DOCS_IN:
    app_kwargs["openapi_url"] = None

app = FastAPI(**app_kwargs)
app.add_middleware(SecurityHeadersMiddleware)

app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "static")), name="static")

app.include_router(auth_router.router)
app.include_router(users_router.router)
app.include_router(dashboard_router.router)
app.include_router(kb_router.router)
app.include_router(tickets_router.router)
app.include_router(notifications_router.router)
app.include_router(activity_router.router)
app.include_router(storage_router.router)


def _wants_html(request: Request) -> bool:
    return "text/html" in request.headers.get("accept", "")


@app.exception_handler(NotAuthenticated)
async def not_authenticated_handler(request: Request, exc: NotAuthenticated):
    if _wants_html(request):
        return RedirectResponse("/auth/login", status_code=303)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404 and _wants_html(request):
        return templates.TemplateResponse(request, "errors/404.html", status_code=404)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    if _wants_html(request):
        return templates.TemplateResponse(request, "errors/500.html", status_code=500)
    return JSONResponse(status_code=500, content={"detail": "Internal Server Error"})


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.get("/")
async def index(request: Request, user: OptionalUser):
    if user:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse(request, "index.html")
