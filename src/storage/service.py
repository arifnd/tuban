from fastapi import UploadFile

from src.exceptions import BadRequestError, PayloadTooLargeError
from src.settings import service as settings_service
from src.storage.client import StorageBackend, get_storage, new_key
from src.storage.constants import CHUNK_SIZE


def file_extension(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return filename.rsplit(".", 1)[1].strip().lower()


def allowed_extensions() -> set[str]:
    return set(settings_service.get("allowed_extensions") or [])


def validate_extension(filename: str | None) -> str:
    extension = file_extension(filename)
    if extension not in allowed_extensions():
        raise BadRequestError(detail="Unsupported file type")
    return extension


def max_upload_size() -> int:
    return int(settings_service.get("upload_max_size"))


async def read_upload(upload: UploadFile) -> bytes:
    buffer = bytearray()
    limit = max_upload_size()
    while True:
        chunk = await upload.read(CHUNK_SIZE)
        if not chunk:
            break
        buffer.extend(chunk)
        if len(buffer) > limit:
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
