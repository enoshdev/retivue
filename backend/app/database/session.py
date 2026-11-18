import time
from typing import AsyncGenerator, Tuple
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine, text
from app.core.config import settings
from app.core.logging import logger

# Async SQLAlchemy engine for FastAPI requests
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_timeout=settings.DB_POOL_TIMEOUT,
    pool_pre_ping=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency injection provider for database sessions with automatic cleanup."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception as exc:
            logger.error(f"Database session error: {exc.__class__.__name__}")
            await session.rollback()
            raise
        finally:
            await session.close()


def get_sync_engine():
    """Sync engine (Psycopg 3) primarily for Alembic migrations and CLI maintenance."""
    return create_engine(
        settings.SYNC_DATABASE_URL,
        pool_pre_ping=True,
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
    )


async def check_db_health() -> Tuple[bool, float, str]:
    """
    Executes a real connectivity check (SELECT 1).
    Returns (is_healthy, latency_ms, message).
    """
    start_time = time.perf_counter()
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(text("SELECT 1;"))
            val = result.scalar()
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            if val == 1:
                return True, latency_ms, "Database connected and responsive."
            return False, latency_ms, "Unexpected database query result."
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
        # Log error securely without exposing credentials
        logger.error(f"Database connectivity check failed: {exc.__class__.__name__}")
        return False, latency_ms, "Database connectivity check failed."
