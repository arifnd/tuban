import os

os.environ.setdefault("ENVIRONMENT", "local")
os.environ.setdefault(
    "DATABASE_URL",
    (
        f"sqlite+aiosqlite:///./instance/test_{os.environ.get('PYTEST_XDIST_WORKER', '')}.db"
        if os.environ.get("PYTEST_XDIST_WORKER")
        else "sqlite+aiosqlite:///./instance/test_batik.db"
    ),
)
os.environ.setdefault("AUTH_SESSION_SECRET", "test-secret-that-is-longer-than-32-bytes-for-hmac")
os.environ.setdefault("INITIAL_ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("STORAGE_LOCAL_DIR", "./instance/test_media")

import pytest
from httpx2 import ASGITransport, AsyncClient

from src.activity import models as activity_models  # noqa: F401
from src.database import SessionFactory, engine
from src.kb import models as kb_models  # noqa: F401
from src.main import app
from src.models import Base
from src.notifications import models as notification_models  # noqa: F401
from src.settings import models as settings_models  # noqa: F401
from src.settings import service as settings_service
from src.tickets import models as ticket_models  # noqa: F401
from src.users import models as user_models  # noqa: F401


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
