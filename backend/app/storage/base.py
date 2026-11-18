from dataclasses import dataclass
from datetime import datetime
from typing import AsyncIterator, Dict, Any
from abc import ABC, abstractmethod


class StorageError(Exception):
    """Base exception raised by private image storage operations without leaking paths."""


class StorageObjectNotFoundError(StorageError):
    """Raised when a requested stored object does not exist."""


class StoragePathSecurityError(StorageError):
    """Raised when a storage key violates path traversal or containment rules."""


class StorageConfigurationError(StorageError):
    """Raised when a storage provider is misconfigured or missing credentials."""


@dataclass(frozen=True)
class StoredObjectInfo:
    storage_key: str
    provider: str
    size_bytes: int
    created_at: datetime


class ImageStorageBackend(ABC):
    """Abstract interface for private retinal image storage providers."""

    provider_name: str = "abstract"

    @abstractmethod
    async def save_bytes(
        self,
        storage_key: str,
        data: bytes,
        content_type: str,
    ) -> StoredObjectInfo:
        """Persist exact raw bytes under a random internal storage_key."""

    @abstractmethod
    async def read_bytes(self, storage_key: str) -> bytes:
        """Retrieve exact stored bytes by storage_key."""

    @abstractmethod
    async def stream_chunks(
        self,
        storage_key: str,
        chunk_size: int = 65536,
    ) -> AsyncIterator[bytes]:
        """Yield raw chunks for authenticated HTTP streaming."""

    @abstractmethod
    async def exists(self, storage_key: str) -> bool:
        """Return True if object currently exists in private storage."""

    @abstractmethod
    async def get_metadata(self, storage_key: str) -> Dict[str, Any]:
        """Return internal object metadata (size_bytes, exists, modified_at) without filesystem paths."""

    @abstractmethod
    async def delete(self, storage_key: str) -> bool:
        """Remove an object from storage (for rollback cleanup or retention purge)."""

