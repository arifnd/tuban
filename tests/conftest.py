import os

os.environ.setdefault("ENVIRONMENT", "local")

# Each xdist worker needs its own SQLite file: the controller process imports
# this module first and sets DATABASE_URL, and the workers inherit that value
# via execnet. Assign the per-worker path explicitly instead of relying on
# setdefault, while preserving a user-provided non-test DATABASE_URL.
if not os.environ.get("DATABASE_URL") or "instance/test" in os.environ.get("DATABASE_URL", ""):
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///./instance/test_{os.environ.get('PYTEST_XDIST_WORKER', 'main')}.db"
os.environ.setdefault("AUTH_SESSION_SECRET", "test-secret-that-is-longer-than-32-bytes-for-hmac")
os.environ.setdefault("AUTH_DEV_LOGIN_ENABLED", "true")
os.environ.setdefault("INITIAL_ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("STORAGE_LOCAL_DIR", "./instance/test_media")

import pytest
from httpx2 import ASGITransport, AsyncClient

from src import models_registry  # noqa: F401  (registers every model on Base.metadata)
from src.database import SessionFactory, engine
from src.main import app
from src.models import Base
from src.settings import service as settings_service


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    settings_service.reset_cache()
    yield
    settings_service.reset_cache()


@pytest.fixture(autouse=True)
async def _db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db():
    async with SessionFactory() as session:
        yield session
