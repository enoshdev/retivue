import os
import json
import tempfile
from typing import List, Union, Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_local_storage_root() -> str:
    base_dir = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    return os.path.join(base_dir, "retivue", "private_storage")


def _default_dataset_root() -> str:
    base_dir = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    return os.path.join(base_dir, "retivue", "datasets")


def _default_model_root() -> str:
    base_dir = os.environ.get("LOCALAPPDATA") or tempfile.gettempdir()
    return os.path.join(base_dir, "retivue", "models")


class Settings(BaseSettings):
    PROJECT_NAME: str = "RETIVUE Clinical Backend"
    APP_ENV: str = "development"
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "retivue-development-secret-key-change-in-production-only"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 30  # 30 days

    # PostgreSQL Database
    POSTGRES_SERVER: str = "127.0.0.1"
    POSTGRES_PORT: int = 5433
    POSTGRES_USER: str = "retivue_user"
    POSTGRES_PASSWORD: str = "RetiVue_Dev_2026_Secure!"
    POSTGRES_DB: str = "retivue"

    # Connection Strings
    DATABASE_URL: str = "postgresql+asyncpg://retivue_user:RetiVue_Dev_2026_Secure!@127.0.0.1:5433/retivue"
    SYNC_DATABASE_URL: str = "postgresql+psycopg://retivue_user:RetiVue_Dev_2026_Secure!@127.0.0.1:5433/retivue"
    TEST_DATABASE_URL: str = "postgresql+asyncpg://retivue_user:RetiVue_Dev_2026_Secure!@127.0.0.1:5433/retivue_test"
    TEST_SYNC_DATABASE_URL: str = "postgresql+psycopg://retivue_user:RetiVue_Dev_2026_Secure!@127.0.0.1:5433/retivue_test"

    # Connection Pool Settings
    DB_POOL_SIZE: int = 5
    DB_MAX_OVERFLOW: int = 10
    DB_POOL_TIMEOUT: int = 30
    DB_CONNECT_TIMEOUT: int = 5

    # Frontend Origin & CORS
    FRONTEND_ORIGIN: str = "http://localhost:3000"
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Session & Cookie Security
    SESSION_COOKIE_NAME: str = "retivue_session"
    SESSION_MAX_AGE_SECONDS: int = 60 * 60 * 24 * 30  # 30 days
    COOKIE_SECURE: bool = False  # Set to True when served over HTTPS
    COOKIE_SAMESITE: str = "lax"
    COOKIE_PATH: str = "/"

    # CSRF Protection
    CSRF_COOKIE_NAME: str = "retivue_csrf"
    CSRF_HEADER_NAME: str = "X-CSRF-Token"

    # Secure Private Image Storage (Phase 4)
    STORAGE_PROVIDER: str = "local"  # 'local' or 's3'
    LOCAL_STORAGE_ROOT: str = _default_local_storage_root()
    S3_BUCKET_NAME: Optional[str] = None
    S3_ENDPOINT_URL: Optional[str] = None
    S3_REGION: str = "ap-south-1"

    # Server-Side Image Upload Validation Limits (Phase 4)
    MAX_UPLOAD_SIZE_BYTES: int = 20 * 1024 * 1024  # 20 MB
    MIN_IMAGE_WIDTH: int = 128
    MIN_IMAGE_HEIGHT: int = 128
    MAX_IMAGE_WIDTH: int = 12000
    MAX_IMAGE_HEIGHT: int = 12000
    MAX_IMAGE_PIXELS: int = 40_000_000  # 40 MP decompression-bomb guard
    ALLOWED_IMAGE_MEDIA_TYPES: List[str] = ["image/jpeg", "image/png"]

    # Research Dataset Engineering Directory (Phase 5 - strictly segregated outside Git/OneDrive)
    DATASET_ROOT: str = _default_dataset_root()

    # AI Model Experiment & Checkpoint Directory (Phase 9 - strictly outside Git/OneDrive)
    MODEL_ROOT: str = _default_model_root()
    DEFAULT_AI_MODEL_KEY: str = "aptos_e2_weighted_sampler"

    def validate_runtime_security(self) -> None:
        """Fail closed if production deployment uses unsafe development defaults."""
        env = (self.APP_ENV or self.ENVIRONMENT or "development").strip().lower()
        if env == "production":
            if self.SECRET_KEY == "retivue-development-secret-key-change-in-production-only" or len(self.SECRET_KEY) < 32:
                raise RuntimeError("Unsafe SECRET_KEY in production mode. Provide a strong random secret (>=32 chars).")
            if not self.COOKIE_SECURE:
                raise RuntimeError("COOKIE_SECURE must be True in production mode.")
            if any("localhost" in origin or "127.0.0.1" in origin for origin in self.BACKEND_CORS_ORIGINS):
                raise RuntimeError("Localhost CORS origins must not be enabled in production mode.")

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            origins = [i.strip() for i in v.split(",") if i.strip()]
            return origins
        elif isinstance(v, str) and v.startswith("["):
            return json.loads(v)
        elif isinstance(v, list):
            return v
        return ["http://localhost:3000"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
