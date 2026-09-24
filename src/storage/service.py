from fastapi import UploadFile

from src.exceptions import BadRequestError, PayloadTooLargeError
from src.storage.client import StorageBackend, get_storage, new_key
from src.storage.config import storage_settings

CHUNK_SIZE = 64 * 1024

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
DOCUMENT_EXTENSIONS = {"pdf", "txt", "csv", "md", "json", "log", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "zip"}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | DOCUMENT_EXTENSIONS


def file_extension(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].strip().lower()


def validate_extension(filename: str | None) -> str:
    extension = file_extension(filename)
    if extension not in ALLOWED_EXTENSIONS:
        raise BadRequestError(detail="Unsupported file type")
    return extension


async def read_upload(upload: UploadFile) -> bytes:
    buffer = bytearray()
    while True:
        chunk = await upload.read(CHUNK_SIZE)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > storage_settings.UPLOAD_MAX_SIZE:
            raise PayloadTooLargeError(detail="File exceeds the upload size limit")
    if not buffer:
        raise BadRequestError(detail="Empty file")
    return bytes(buffer)


async def save_upload(upload: UploadFile, prefix: str, backend: StorageBackend | None = None) -> tuple[str, str, int]:
    """Validate and persist an upload. Returns ``(key, filename, size)``."""
    if not upload.filename:
        raise BadRequestError(detail="Missing filename")
    extension = validate_extension(upload.filename)
    content = await read_upload(upload)
    key = new_key(prefix, upload.filename)
    if not key.endswith(f".{extension}"):
        key = f"{key}.{extension}"
    await (backend or get_storage()).save(content, key)
    return key, upload.filename, len(content)


async def delete_upload(key: str, backend: StorageBackend | None = None) -> None:
    await (backend or get_storage()).delete(key)
