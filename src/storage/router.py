import mimetypes
import uuid
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

from src.auth.dependencies import CurrentUser, DbDep
from src.exceptions import NotFoundError
from src.storage.client import MEDIA_DIR
from src.storage.config import storage_settings
from src.tickets.models import Ticket

router = APIRouter(tags=["storage"])


def _media_root() -> Path:
    return Path(storage_settings.LOCAL_DIR) if storage_settings.LOCAL_DIR else MEDIA_DIR


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

    media_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
    return FileResponse(target, media_type=media_type, headers={"Content-Disposition": "inline", "X-Content-Type-Options": "nosniff"})
