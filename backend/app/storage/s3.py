from typing import AsyncIterator, Dict, Any, Optional
from app.storage.base import (
    ImageStorageBackend,
    StoredObjectInfo,
    StorageConfigurationError,
)


class S3CompatibleStorage(ImageStorageBackend):
    """
    Future production S3-compatible object storage adapter boundary.
    Not active in local development; requires explicit bucket configuration and SDK provisioning.
    """

    provider_name = "s3"

    def __init__(
        self,
        bucket_name: Optional[str],
        endpoint_url: Optional[str] = None,
        region: str = "ap-south-1",
    ) -> None:
        if not bucket_name:
            raise StorageConfigurationError(
                "S3 storage provider selected, but S3_BUCKET_NAME is not configured."
            )
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.region = region

    def _not_implemented(self) -> StorageConfigurationError:
        return StorageConfigurationError(
            "S3-compatible storage adapter is reserved for future cloud deployment "
            "and is not provisioned in this environment."
        )

    async def save_bytes(
        self,
        storage_key: str,
        data: bytes,
        content_type: str,
    ) -> StoredObjectInfo:
        raise self._not_implemented()

    async def read_bytes(self, storage_key: str) -> bytes:
        raise self._not_implemented()

    async def stream_chunks(
        self,
        storage_key: str,
        chunk_size: int = 65536,
    ) -> AsyncIterator[bytes]:
        if False:
            yield b""
        raise self._not_implemented()

    async def exists(self, storage_key: str) -> bool:
        raise self._not_implemented()

    async def get_metadata(self, storage_key: str) -> Dict[str, Any]:
        raise self._not_implemented()

    async def delete(self, storage_key: str) -> bool:
        raise self._not_implemented()

