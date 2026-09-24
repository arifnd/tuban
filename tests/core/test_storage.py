import io

import pytest
from httpx2 import AsyncClient
from starlette.datastructures import Headers, UploadFile

from src.exceptions import BadRequestError, PayloadTooLargeError
from src.storage import service as storage_service
from src.storage.client import LocalStorage, S3Storage, get_storage, new_key
from src.storage.config import storage_settings
from tests.tickets.helpers import login, make_user


class _FakeS3Client:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}

    def put_object(self, Bucket, Key, Body):  # noqa: N803
        self.objects[Key] = Body

    def delete_object(self, Bucket, Key):  # noqa: N803
        self.objects.pop(Key, None)


class _S3Config:
    AWS_S3_BUCKET = "bucket"
    AWS_ENDPOINT_URL = ""
    AWS_DEFAULT_REGION = ""
    AWS_ACCESS_KEY_ID = ""
    AWS_SECRET_ACCESS_KEY = ""


def _upload(name: str, content: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(content), filename=name, headers=Headers({"content-type": "text/plain"}))


def test_new_key_sanitizes_filename() -> None:
    key = new_key("kb/1", "my file!.txt")
    assert key.startswith("kb/1/")
    assert " " not in key


async def test_local_storage_roundtrip(tmp_path) -> None:
    backend = LocalStorage(root=tmp_path)
    url = await backend.save(b"data", "a/b.txt")
    assert url == "/media/a/b.txt"
    assert (tmp_path / "a" / "b.txt").read_bytes() == b"data"
    await backend.delete("a/b.txt")
    assert not (tmp_path / "a" / "b.txt").exists()
    await backend.delete("missing.txt")


async def test_s3_storage_with_fake_client() -> None:
    client = _FakeS3Client()
    backend = S3Storage(config=_S3Config(), client=client)
    url = await backend.save(b"x", "k.txt")
    assert url == "/media/k.txt"
    assert client.objects["k.txt"] == b"x"
    await backend.delete("k.txt")
    assert "k.txt" not in client.objects


def test_get_storage_s3(monkeypatch) -> None:
    monkeypatch.setattr(storage_settings, "BACKEND", "s3")
    monkeypatch.setattr(storage_settings, "AWS_S3_BUCKET", "bucket")
    assert isinstance(get_storage(), S3Storage)


async def test_save_upload_rejects_bad_extension() -> None:
    with pytest.raises(BadRequestError):
        await storage_service.save_upload(_upload("evil.exe", b"MZ"), "kb/1")


async def test_save_upload_rejects_empty_file() -> None:
    with pytest.raises(BadRequestError):
        await storage_service.save_upload(_upload("note.txt", b""), "kb/1")


async def test_save_upload_rejects_oversized(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(storage_settings, "UPLOAD_MAX_SIZE", 2)
    with pytest.raises(PayloadTooLargeError):
        await storage_service.save_upload(_upload("note.txt", b"too large"), "kb/1", backend=LocalStorage(root=tmp_path))


async def test_save_upload_ok(tmp_path) -> None:
    key, name, size = await storage_service.save_upload(_upload("note.txt", b"hi"), "kb/1", backend=LocalStorage(root=tmp_path))
    assert name == "note.txt"
    assert size == 2
    assert key.startswith("kb/1/")


async def test_media_route_rejects_bad_paths(client: AsyncClient, db) -> None:
    await make_user(db, "u@example.com")
    await login(client, "u@example.com")
    assert (await client.get("/media/nope")).status_code == 404
    assert (await client.get("/media/other/abc/x.txt")).status_code == 404
    assert (await client.get("/media/kb/not-a-uuid/x.txt")).status_code == 404
    assert (await client.get("/media/kb/00000000-0000-0000-0000-000000000000/missing.txt")).status_code == 404


async def test_media_route_missing_file(client: AsyncClient, db) -> None:
    from src.kb.models import KbArticleStatus, KbArticleVisibility
    from tests.kb.helpers import make_article, make_editor

    editor = await make_editor(db, "editor@example.com")
    article = await make_article(db, editor, title="Visible", status=KbArticleStatus.PUBLISHED, visibility=KbArticleVisibility.PUBLIC)
    await login(client, "editor@example.com")
    assert (await client.get(f"/media/kb/{article.id}/missing.txt")).status_code == 404
