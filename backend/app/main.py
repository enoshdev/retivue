from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.config import settings
from app.core.logging import logger
from app.api.routes.health import router as health_router
from app.api.routes.auth import router as auth_router
from app.api.routes.patients import router as patients_router
from app.api.routes.screenings import router as screenings_router
from app.api.routes.clinical_workflow import router as clinical_workflow_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown event logging and safety validation."""
    settings.validate_runtime_security()
    logger.info(f"Starting {settings.PROJECT_NAME} in '{settings.APP_ENV}' mode.")
    logger.info(f"CORS allowed origins configured: {settings.BACKEND_CORS_ORIGINS}")
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Backend API and database foundation for RETIVUE AI-assisted diabetic retinopathy screening.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Strict CORS Middleware configured to permitted frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Requested-With", "X-CSRF-Token", "x-csrf-token"],
    expose_headers=["Content-Disposition", "ETag", "Content-Length"],
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Structured handler for validation errors."""
    errors = []
    for err in exc.errors():
        field = " -> ".join([str(loc) for loc in err.get("loc", [])])
        errors.append(f"{field}: {err.get('msg')}")
    logger.warning(f"Validation error on {request.method} {request.url.path}: {errors}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={"detail": "Validation error: " + "; ".join(errors)}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Catches unhandled errors without leaking system internals."""
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc.__class__.__name__}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal server error occurred. Please try again later."}
    )


# Include API routers under /api
app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(patients_router, prefix="/api")
app.include_router(screenings_router, prefix="/api")
app.include_router(clinical_workflow_router, prefix="/api")


@app.get("/", tags=["Root"])
async def root():
    """Root informative index."""
    return {
        "project": settings.PROJECT_NAME,
        "environment": settings.APP_ENV,
        "status": "operational",
        "docs": "/docs",
        "health": "/api/health",
        "database_health": "/api/health/database"
    }
