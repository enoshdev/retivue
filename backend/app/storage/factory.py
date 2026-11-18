from app.core.config import settings
from app.storage.base import ImageStorageBackend, StorageConfigurationError
from app.storage.local import LocalFilesystemStorage
from app.storage.s3 import S3CompatibleStorage


def get_image_storage() -> ImageStorageBackend:
    """
    Configuration-based storage backend factory.
    Supports FastAPI dependency override for isolated temporary test storage.
    """
    provider = (settings.STORAGE_PROVIDER or "local").strip().lower()
    if provider == "local":
        return LocalFilesystemStorage(settings.LOCAL_STORAGE_ROOT)
    if provider == "s3":
        return S3CompatibleStorage(
            bucket_name=settings.S3_BUCKET_NAME,
            endpoint_url=settings.S3_ENDPOINT_URL,
            region=settings.S3_REGION,
        )
    raise StorageConfigurationError(f"Unsupported storage provider '{settings.STORAGE_PROVIDER}'.")

