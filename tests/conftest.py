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
from sqlalchemy.ext.asyncio import async_sessionmaker

from src import models_registry  # noqa: F401  (registers every model on Base.metadata)
from src.database import engine
from src.main import app
from src.models import Base
from src.ratelimit import rate_limiter
from src.settings import service as settings_service

# Test setup uses an autocommit session: services only flush now, and a long-lived
# transactional session would keep SQLite locks open across HTTP requests. The app
# itself keeps its transactional get_db boundary.
TestSessionFactory = async_sessionmaker(engine.execution_options(isolation_level="AUTOCOMMIT"), expire_on_commit=False)


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    settings_service.reset_cache()
    rate_limiter.clear()
    yield
    settings_service.reset_cache()
    rate_limiter.clear()


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
    # raise_app_exceptions=False mirrors a real server, where an unhandled 500 is
    # returned to the client rather than propagated.
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def db():
    async with TestSessionFactory() as session:
        yield session
