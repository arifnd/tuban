import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from src.auth.dependencies import CurrentUser, DbDep
from src.exceptions import NotFoundError
from src.storage.client import MEDIA_DIR
from src.storage.config import storage_settings
from src.storage.constants import IMAGE_EXTENSIONS
from src.tickets.models import Ticket

router = APIRouter(tags=["storage"])


def _media_root() -> Path:
    return Path(storage_settings.LOCAL_DIR) if storage_settings.LOCAL_DIR else MEDIA_DIR


def _media_response(target: Path) -> FileResponse:
    """Render known image types inline; download everything else.

    User uploads live on the app origin, so anything that is not a raster image is
    forced to an attachment with an opaque content type to prevent stored XSS.
    """
    extension = target.suffix.lstrip(".").lower()
    media_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
    if extension in IMAGE_EXTENSIONS and media_type.startswith("image/"):
        return FileResponse(target, media_type=media_type, headers={"Content-Disposition": "inline", "X-Content-Type-Options": "nosniff"})
    return FileResponse(target, media_type="application/octet-stream", filename=target.name, headers={"X-Content-Type-Options": "nosniff"})


@router.get("/media/carousel/{filename}")
async def serve_carousel_media(filename: str):
    if Path(filename).name != filename or Path(filename).suffix.lstrip(".").lower() not in IMAGE_EXTENSIONS:
        raise NotFoundError()

    root = _media_root().resolve()
    target = (root / "carousel" / filename).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise NotFoundError()

    return _media_response(target)


@router.get("/media/{path:path}")
async def serve_media(path: str, user: CurrentUser, db: DbDep):
    parts = path.split("/")
    if len(parts) < 3 or parts[0] not in {"kb", "tickets"}:
        raise NotFoundError()
    try:
        owner_id = uuid.UUID(parts[1])
    except ValueError:
        raise NotFoundError() from None

    if parts[0] == "kb":
        from src.kb import service as kb_service

        if await kb_service.get_article_by_id(db, owner_id, viewer=user) is None:
            raise NotFoundError()
    else:
        from src.tickets import service as ticket_service

        ticket = await db.get(Ticket, owner_id)
        if ticket is None or not ticket_service.user_can_access_ticket(ticket, user):
            raise NotFoundError()

    root = _media_root().resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root) or not target.is_file():
        raise NotFoundError()

    return _media_response(target)
