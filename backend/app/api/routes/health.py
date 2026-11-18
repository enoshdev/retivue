from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.database.session import check_db_health
from app.schemas.health import BackendHealthResponse, DatabaseHealthResponse

router = APIRouter(prefix="", tags=["Health"])


@router.get(
    "/health",
    response_model=BackendHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Backend Service Health",
    description="Reports the live operational availability of the FastAPI application."
)
async def get_backend_health():
    """Returns actual backend application availability."""
    return BackendHealthResponse(
        status="healthy",
        project=settings.PROJECT_NAME,
        environment=settings.APP_ENV,
        version="1.0.0"
    )


@router.get(
    "/health/database",
    response_model=DatabaseHealthResponse,
    responses={
        200: {"description": "Database is connected and responsive"},
        503: {"description": "Database connection failed or timed out"}
    },
    summary="Database Connectivity Health",
    description="Performs an authentic SQL query against PostgreSQL to verify connectivity and latency."
)
async def get_database_health():
    """Performs an authentic SELECT 1 check against the PostgreSQL database."""
    is_healthy, latency_ms, message = await check_db_health()

    payload = DatabaseHealthResponse(
        status="healthy" if is_healthy else "unhealthy",
        database="connected" if is_healthy else "disconnected",
        latency_ms=latency_ms,
        message=message
    )

    if is_healthy:
        return payload

    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump()
    )
