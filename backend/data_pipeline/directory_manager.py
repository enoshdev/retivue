import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
from app.core.config import settings


class DatasetDirectoryError(Exception):
    """Raised when dataset root validation or directory creation fails."""


SUPPORTED_DATASET_NAMES = ("aptos", "idrid", "messidor2", "drive")


@dataclass(frozen=True)
class DatasetDirectories:
    root: Path
    archives: Path
    archives_by_dataset: Dict[str, Path]
    raw: Path
    raw_by_dataset: Dict[str, Path]
    manifests: Path
    processed: Path
    rejected: Path
    reports: Path
    temporary: Path


class DatasetDirectoryManager:
    """
    Provisions and guards the configurable research dataset directory structure
    strictly outside the Git repository, OneDrive workspace, public static directories,
    and clinical patient storage.
    """

    def __init__(self, root_override: Optional[str] = None) -> None:
        raw_root = root_override or settings.DATASET_ROOT
        if not raw_root or not str(raw_root).strip():
            raise DatasetDirectoryError("DATASET_ROOT cannot be empty.")
        self._root = Path(raw_root).resolve()
        self._validate_safe_location()

    @property
    def root(self) -> Path:
        return self._root

    def _validate_safe_location(self) -> None:
        """Ensure research dataset directory never overlaps clinical patient storage or Next.js public assets."""
        clinical_storage = Path(settings.LOCAL_STORAGE_ROOT).resolve()
        repo_root = Path(__file__).resolve().parent.parent.parent
        public_dir = (repo_root / "public").resolve()
        src_dir = (repo_root / "src").resolve()

        for forbidden_name, forbidden_path in (
            ("clinical patient storage", clinical_storage),
            ("Next.js public static directory", public_dir),
            ("frontend source directory", src_dir),
        ):
            if self._root == forbidden_path or forbidden_path in self._root.parents or self._root in forbidden_path.parents:
                raise DatasetDirectoryError(
                    f"DATASET_ROOT '{self._root}' conflicts with {forbidden_name} '{forbidden_path}'."
                )

    def ensure_structure(self) -> DatasetDirectories:
        """Create required dataset subdirectories cleanly, surfacing permission/filesystem errors explicitly."""
        try:
            self._root.mkdir(parents=True, exist_ok=True)
            archives_dir = self._root / "archives"
            archives_dir.mkdir(parents=True, exist_ok=True)
            archives_by_dataset: Dict[str, Path] = {}
            for name in SUPPORTED_DATASET_NAMES:
                arch_ds_dir = archives_dir / name
                arch_ds_dir.mkdir(parents=True, exist_ok=True)
                archives_by_dataset[name] = arch_ds_dir

            raw_dir = self._root / "raw"
            raw_dir.mkdir(parents=True, exist_ok=True)

            raw_by_dataset: Dict[str, Path] = {}
            for name in SUPPORTED_DATASET_NAMES:
                ds_dir = raw_dir / name
                ds_dir.mkdir(parents=True, exist_ok=True)
                raw_by_dataset[name] = ds_dir

            manifests = self._root / "manifests"
            processed = self._root / "processed"
            rejected = self._root / "rejected"
            reports = self._root / "reports"
            temporary = self._root / "temporary"

            for d in (manifests, processed, rejected, reports, temporary):
                d.mkdir(parents=True, exist_ok=True)

            # Verify writability
            if not os.access(self._root, os.W_OK):
                raise PermissionError(f"Dataset directory '{self._root}' is not writable.")

            return DatasetDirectories(
                root=self._root,
                archives=archives_dir,
                archives_by_dataset=archives_by_dataset,
                raw=raw_dir,
                raw_by_dataset=raw_by_dataset,
                manifests=manifests,
                processed=processed,
                rejected=rejected,
                reports=reports,
                temporary=temporary,
            )
        except OSError as exc:
            raise DatasetDirectoryError(
                f"Failed to provision dataset directory architecture at '{self._root}': {exc}"
            ) from exc
