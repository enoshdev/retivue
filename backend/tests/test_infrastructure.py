import pytest
from httpx import AsyncClient
from sqlalchemy import text
from app.main import app
from app.core.config import settings
from unittest.mock import patch


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    """Verify root index endpoint responds with project status."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["project"] == settings.PROJECT_NAME
    assert data["status"] == "operational"
    assert "health" in data
    assert "database_health" in data


@pytest.mark.asyncio
async def test_backend_health_endpoint(client: AsyncClient):
    """Verify backend health endpoint reports operational availability."""
    response = await client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["project"] == settings.PROJECT_NAME
    assert data["environment"] == settings.APP_ENV
    assert "version" in data


@pytest.mark.asyncio
async def test_database_health_endpoint_success(client: AsyncClient):
    """Verify real database connectivity check succeeds against running PostgreSQL."""
    response = await client.get("/api/health/database")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"
    assert isinstance(data["latency_ms"], (int, float))
    assert data["latency_ms"] >= 0
    assert "responsive" in data["message"].lower()


@pytest.mark.asyncio
async def test_database_health_endpoint_failure_handling(client: AsyncClient):
    """Verify database health endpoint returns HTTP 503 and safe diagnostic message on failure."""
    with patch("app.api.routes.health.check_db_health") as mock_check:
        mock_check.return_value = (False, 25.4, "Database connectivity check failed.")
        response = await client.get("/api/health/database")
        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "unhealthy"
        assert data["database"] == "disconnected"
        assert data["latency_ms"] == 25.4
        # Assert no sensitive credentials leaked
        assert "password" not in response.text.lower()
        assert "secret" not in response.text.lower()


@pytest.mark.asyncio
async def test_cors_allowed_frontend_origin(client: AsyncClient):
    """Verify that requests from the approved frontend origin (http://localhost:3000) are permitted."""
    headers = {
        "Origin": "http://localhost:3000",
        "Accept": "application/json"
    }
    response = await client.get("/api/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert response.headers.get("access-control-allow-credentials") == "true"


@pytest.mark.asyncio
async def test_cors_preflight_options(client: AsyncClient):
    """Verify preflight OPTIONS requests from frontend origin return correct headers."""
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "Content-Type"
    }
    response = await client.options("/api/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:3000"


@pytest.mark.asyncio
async def test_cors_disallowed_origin(client: AsyncClient):
    """Verify that an untrusted origin does NOT receive CORS credentials approval."""
    headers = {
        "Origin": "http://untrusted-domain.com",
        "Accept": "application/json"
    }
    response = await client.get("/api/health", headers=headers)
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") != "http://untrusted-domain.com"


@pytest.mark.asyncio
async def test_alembic_migration_recorded_in_postgres():
    """Verify that the Alembic migration history is genuinely recorded in the PostgreSQL database."""
    from tests.conftest import test_engine
    async with test_engine.connect() as conn:
        result = await conn.execute(text("SELECT version_num FROM alembic_version;"))
        version = result.scalar()
        assert version is not None
        assert version == "b8d5e0f1a234"


@pytest.mark.asyncio
async def test_unhandled_route_returns_404(client: AsyncClient):
    """Verify non-existent routes return structured 404."""
    response = await client.get("/api/nonexistent-route")
    assert response.status_code == 404

