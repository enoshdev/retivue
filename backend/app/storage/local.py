import os
import re
import uuid
import secrets
from pathlib import Path
from datetime import datetime, timezone
from typing import AsyncIterator, Dict, Any
import anyio
from app.storage.base import (
    ImageStorageBackend,
    StoredObjectInfo,
    StorageError,
    StorageObjectNotFoundError,
    StoragePathSecurityError,
)

# Strict safe storage key pattern: lowercase hex / digits / slashes / dot / dash / underscore
_SAFE_KEY_RE = re.compile(r"^[a-zA-Z0-9/_-]+\.[a-zA-Z0-9]+$")


def generate_storage_key(screening_id: str, eye: str, file_extension: str) -> str:
    """
    Generate an opaque, unguessable storage key unrelated to user-supplied filenames.
    Example: screenings/<screening_uuid>/od/<uuid4>_<random_hex>.jpg
    """
    ext = file_extension.lower().lstrip(".")
    safe_screening = re.sub(r"[^a-zA-Z0-9_-]", "", screening_id)
    safe_eye = "od" if eye == "OD" else "os"
    random_token = f"{uuid.uuid4().hex}_{secrets.token_hex(8)}"
    return f"screenings/{safe_screening}/{safe_eye}/{random_token}.{ext}"


class LocalFilesystemStorage(ImageStorageBackend):
    """
    Private local filesystem image storage outside OneDrive and public Next.js directories.
    Prevents path traversal and writes atomically.
    """

    provider_name = "local"

    def __init__(self, root_dir: str) -> None:
        self._root = Path(root_dir).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "posix":
                os.chmod(self._root, 0o700)
        except OSError:
            pass

    @property
    def root_dir(self) -> Path:
        return self._root

    def _resolve_safe_path(self, storage_key: str) -> Path:
        if not storage_key or ".." in storage_key or storage_key.startswith(("/", "\\")):
            raise StoragePathSecurityError("Invalid storage key structure.")
        if not _SAFE_KEY_RE.match(storage_key):
            raise StoragePathSecurityError("Storage key contains disallowed characters.")

        candidate = (self._root / storage_key).resolve()
        # Strict containment check
        try:
            candidate.relative_to(self._root)
        except ValueError as exc:
            raise StoragePathSecurityError("Storage path escapes private storage root.") from exc

        return candidate

    async def save_bytes(
        self,
        storage_key: str,
        data: bytes,
        content_type: str,
    ) -> StoredObjectInfo:
        del content_type  # Stored in DB metadata; raw binary preserved unmodified on disk
        target_path = self._resolve_safe_path(storage_key)

        def _write_sync() -> int:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            if os.name == "posix":
                try:
                    os.chmod(target_path.parent, 0o700)
                except OSError:
                    pass

            tmp_path = target_path.with_suffix(target_path.suffix + f".tmp.{secrets.token_hex(4)}")
            try:
                with open(tmp_path, "wb") as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
                if os.name == "posix":
                    os.chmod(tmp_path, 0o600)
                os.replace(tmp_path, target_path)
            except Exception as exc:
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except OSError:
                        pass
                raise StorageError("Failed to persist retinal image to private storage.") from exc

            return len(data)

        size_bytes = await anyio.to_thread.run_sync(_write_sync)
        return StoredObjectInfo(
            storage_key=storage_key,
            provider=self.provider_name,
            size_bytes=size_bytes,
            created_at=datetime.now(timezone.utc),
        )

    async def read_bytes(self, storage_key: str) -> bytes:
        target_path = self._resolve_safe_path(storage_key)

        def _read_sync() -> bytes:
            if not target_path.is_file():
                raise StorageObjectNotFoundError("Stored retinal image object is missing.")
            with open(target_path, "rb") as f:
                return f.read()

        return await anyio.to_thread.run_sync(_read_sync)

    async def stream_chunks(
        self,
        storage_key: str,
        chunk_size: int = 65536,
    ) -> AsyncIterator[bytes]:
        target_path = self._resolve_safe_path(storage_key)

        def _check_exists() -> bool:
            return target_path.is_file()

        if not await anyio.to_thread.run_sync(_check_exists):
            raise StorageObjectNotFoundError("Stored retinal image object is missing.")

        f = open(target_path, "rb")
        try:
            while True:
                chunk = await anyio.to_thread.run_sync(f.read, chunk_size)
                if not chunk:
                    break
                yield chunk
        finally:
            await anyio.to_thread.run_sync(f.close)

    async def exists(self, storage_key: str) -> bool:
        try:
            target_path = self._resolve_safe_path(storage_key)
        except StoragePathSecurityError:
            return False
        return await anyio.to_thread.run_sync(target_path.is_file)

    async def get_metadata(self, storage_key: str) -> Dict[str, Any]:
        target_path = self._resolve_safe_path(storage_key)

        def _stat_sync() -> Dict[str, Any]:
            if not target_path.is_file():
                raise StorageObjectNotFoundError("Stored retinal image object is missing.")
            st = target_path.stat()
            return {
                "storage_key": storage_key,
                "provider": self.provider_name,
                "size_bytes": st.st_size,
                "modified_at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat(),
            }

        return await anyio.to_thread.run_sync(_stat_sync)

    async def delete(self, storage_key: str) -> bool:
        try:
            target_path = self._resolve_safe_path(storage_key)
        except StoragePathSecurityError:
            return False

        def _delete_sync() -> bool:
            if target_path.is_file():
                target_path.unlink()
                return True
            return False

        return await anyio.to_thread.run_sync(_delete_sync)
