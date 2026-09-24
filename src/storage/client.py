import asyncio
import uuid
from abc import ABC, abstractmethod
from pathlib import Path

import boto3

from src.config import PROJECT_ROOT
from src.storage.config import storage_settings

MEDIA_DIR = PROJECT_ROOT / "media"


def _safe_filename(name: str) -> str:
    cleaned = "".join(ch for ch in (name or "") if ch.isalnum() or ch in {".", "_", "-"}).strip(".-")
    return cleaned or "file"


def new_key(prefix: str, filename: str) -> str:
    return f"{prefix.strip('/')}/{uuid.uuid4().hex}-{_safe_filename(filename)}"


class StorageBackend(ABC):
    @abstractmethod
    async def save(self, content: bytes, key: str) -> str:
        """Persist content at key and return the path/URL used to serve it."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove the object at key (no-op if it does not exist)."""


class LocalStorage(StorageBackend):
    def __init__(self, root: Path | None = None, base_url: str = "/media") -> None:
        self.root = root or (Path(storage_settings.LOCAL_DIR) if storage_settings.LOCAL_DIR else MEDIA_DIR)
        self.base_url = base_url.rstrip("/")

    async def save(self, content: bytes, key: str) -> str:
        path = self.root / key
        path.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(path.write_bytes, content)
        return f"{self.base_url}/{key}"

    async def delete(self, key: str) -> None:
        path = self.root / key
        await asyncio.to_thread(lambda: path.unlink(missing_ok=True))


class S3Storage(StorageBackend):
    def __init__(self, config=storage_settings, client=None) -> None:
        self.bucket = config.AWS_S3_BUCKET
        if not self.bucket:
            raise RuntimeError("STORAGE_AWS_S3_BUCKET is required when STORAGE_BACKEND=s3")
        if client is None:
            kwargs: dict = {}
            if config.AWS_ENDPOINT_URL:
                kwargs["endpoint_url"] = config.AWS_ENDPOINT_URL
            client = boto3.client(
                "s3",
                aws_access_key_id=config.AWS_ACCESS_KEY_ID or None,
                aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY or None,
                region_name=config.AWS_DEFAULT_REGION or None,
                **kwargs,
            )
        self.client = client

    async def save(self, content: bytes, key: str) -> str:
        await asyncio.to_thread(self.client.put_object, Bucket=self.bucket, Key=key, Body=content)
        return f"/media/{key}"

    async def delete(self, key: str) -> None:
        await asyncio.to_thread(self.client.delete_object, Bucket=self.bucket, Key=key)


def get_storage() -> StorageBackend:
    if storage_settings.BACKEND == "s3":
        return S3Storage()
    return LocalStorage()
