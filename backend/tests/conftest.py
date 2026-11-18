import sys
import os
import tempfile
from pathlib import Path
from typing import AsyncGenerator

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.main import app
from app.core.config import settings
from app.database.session import get_db
from app.storage import LocalFilesystemStorage, get_image_storage

# Safety guard: ensure pytest NEVER connects to the development database
assert settings.TEST_DATABASE_URL.endswith("/retivue_test"), (
    "Pytest MUST run against the isolated retivue_test database!"
)
assert settings.TEST_SYNC_DATABASE_URL.endswith("/retivue_test"), (
    "Pytest migrations MUST target retivue_test database!"
)

# Use NullPool in tests to prevent cross-event-loop connection reuse on Windows
test_engine = create_async_engine(
    settings.TEST_DATABASE_URL,
    echo=False,
    poolclass=NullPool,
)

TestAsyncSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestAsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


app.dependency_overrides[get_db] = override_get_db


def _run_test_migrations() -> None:
    """Apply Alembic migrations cleanly to the isolated retivue_test PostgreSQL database."""
    backend_dir = Path(__file__).resolve().parent.parent
    alembic_cfg = Config(str(backend_dir / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(backend_dir / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", settings.TEST_SYNC_DATABASE_URL)

    # Point settings.SYNC_DATABASE_URL temporarily during env.py evaluation
    prev_sync = settings.SYNC_DATABASE_URL
    settings.SYNC_DATABASE_URL = settings.TEST_SYNC_DATABASE_URL
    try:
        command.upgrade(alembic_cfg, "head")
    finally:
        settings.SYNC_DATABASE_URL = prev_sync


@pytest.fixture(scope="session", autouse=True)
def initialize_isolated_test_environment():
    """
    Runs once per test session:
    1. Applies Alembic migrations to isolated retivue_test DB.
    2. Provisions an isolated temporary file storage root outside project/public dirs.
    """
    _run_test_migrations()

    with tempfile.TemporaryDirectory(prefix="retivue_test_storage_") as tmp_dir:
        storage_instance = LocalFilesystemStorage(tmp_dir)
        app.dependency_overrides[get_image_storage] = lambda: storage_instance
        yield storage_instance
        app.dependency_overrides.pop(get_image_storage, None)


@pytest.fixture
def test_storage(initialize_isolated_test_environment) -> LocalFilesystemStorage:
    """Provides access to the isolated temporary local storage instance for assertions."""
    return initialize_isolated_test_environment


class CSRFAutoClient(AsyncClient):
    """AsyncClient that automatically propagates X-CSRF-Token header if retivue_csrf cookie is present."""
    async def request(self, method, url, **kwargs):
        headers = dict(kwargs.get("headers") or {})
        csrf_val = self.cookies.get(settings.CSRF_COOKIE_NAME)
        if csrf_val and settings.CSRF_HEADER_NAME not in headers and "x-csrf-token" not in headers:
            headers[settings.CSRF_HEADER_NAME] = csrf_val
        kwargs["headers"] = headers
        return await super().request(method, url, **kwargs)


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with CSRFAutoClient(transport=transport, base_url="http://test") as ac:
        yield ac
