from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse
from starlette.datastructures import UploadFile

from src.auth.dependencies import CsrfDep, DbDep
from src.exceptions import BadRequestError
from src.settings import service as settings_service
from src.storage import service as storage_service
from src.storage.constants import IMAGE_EXTENSIONS
from src.templating import templates
from src.users.dependencies import AdminUser

router = APIRouter(prefix="/carousel", tags=["carousel"])

MAX_SLIDES = 8
MAX_TITLE = 150
MAX_SUBTITLE = 300


def _row_indices(form) -> set[int]:
    indices: set[int] = set()
    for key in form:
        prefix, _, suffix = key.rpartition("_")
        if prefix in {"title", "subtitle", "image", "file"} and suffix.isdigit():
            indices.add(int(suffix))
    return indices


@router.get("")
async def carousel_page(request: Request, db: DbDep, _: AdminUser):
    return templates.TemplateResponse(
        request,
        "carousel/index.html",
        {
            "slides": settings_service.carousel_slides(),
            "saved": request.query_params.get("saved") == "1",
            "max_slides": MAX_SLIDES,
            "max_upload_size_mb": round(int(settings_service.get("upload_max_size")) / (1024 * 1024)),
        },
    )


@router.post("")
async def update_carousel(request: Request, db: DbDep, admin: AdminUser, _: CsrfDep):
    form = await request.form()
    indices = sorted(_row_indices(form))
    if len(indices) > MAX_SLIDES:
        raise BadRequestError(detail=f"A maximum of {MAX_SLIDES} slides is allowed")

    slides: list[dict[str, str]] = []
    for index in indices:
        title = str(form.get(f"title_{index}") or "").strip()
        subtitle = str(form.get(f"subtitle_{index}") or "").strip()
        image = str(form.get(f"image_{index}") or "").strip()
        if len(title) > MAX_TITLE or len(subtitle) > MAX_SUBTITLE:
            raise BadRequestError(detail="Slide text is too long")

        upload = form.get(f"file_{index}")
        if isinstance(upload, UploadFile) and upload.filename:
            if storage_service.file_extension(upload.filename) not in IMAGE_EXTENSIONS:
                raise BadRequestError(detail="Carousel images must be an image file")
            key, _, _ = await storage_service.save_upload(upload, prefix="carousel")
            image = f"/media/{key}"

        if not image:
            continue
        slides.append({"image": image, "title": title, "subtitle": subtitle})

    await settings_service.update(db, admin, {"carousel_slides": slides})
    return RedirectResponse("/carousel?saved=1", status_code=status.HTTP_303_SEE_OTHER)
