"""Archive ingestion, integrity verification, overwrite protection, and raw checksum verification."""

import hashlib
import json
import os
import shutil
import tarfile
import uuid
import zipfile
import zlib
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from data_pipeline.directory_manager import DatasetDirectories
from data_pipeline.manifest import read_manifest_jsonl
from data_pipeline.registry import VERIFIED_DATASET_REGISTRY


class ArchiveImportError(Exception):
    """Raised when archive integrity, path safety, or extraction validation fails."""


@dataclass(frozen=True)
class ArchiveImportRecord:
    dataset_name: str
    source_url: str
    acquired_at_utc: str
    source_archive_input: str
    archive_filename: str
    preserved_archive_path: Optional[str]
    archive_sha256: Optional[str]
    archive_size_bytes: Optional[int]
    extracted_files_count: int
    status: str  # 'imported', 'missing_archive', 'corrupt_archive', 'checksum_mismatch', 'interrupted_import', 'overwrite_blocked', 'insufficient_disk_space'
    error_detail: Optional[str] = None


def compute_file_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute SHA-256 hex digest in streamed chunks so multi-GB archives stay memory-safe."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def check_kaggle_credentials_present() -> Dict[str, Any]:
    """Read-only check for standard Kaggle credentials without bypassing authentication."""
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    env_user = bool((os.environ.get("KAGGLE_USERNAME") or "").strip())
    env_key = bool((os.environ.get("KAGGLE_KEY") or "").strip())
    return {
        "kaggle_json_exists": kaggle_json.is_file(),
        "kaggle_env_vars_present": env_user and env_key,
        "any_kaggle_credentials_present": kaggle_json.is_file() or (env_user and env_key),
    }


def _count_files(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    return sum(1 for p in directory.rglob("*") if p.is_file())


def _append_acquisition_log(manifests_dir: Path, record: ArchiveImportRecord) -> Path:
    manifests_dir.mkdir(parents=True, exist_ok=True)
    log_path = manifests_dir / f"{record.dataset_name}_acquisition_log.jsonl"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    return log_path


def _is_safe_member_path(stage_root: Path, member_name: str) -> Path:
    """Guard against Zip Slip / Tar Slip directory traversal and absolute targets."""
    if not member_name or member_name.startswith(("/", "\\")):
        raise ArchiveImportError(f"Unsafe absolute archive member path rejected: '{member_name}'")
    candidate = (stage_root / member_name).resolve()
    root_resolved = stage_root.resolve()
    if candidate != root_resolved and root_resolved not in candidate.parents:
        raise ArchiveImportError(f"Archive path traversal rejected: '{member_name}'")
    return candidate


def _extract_archive_to_stage(
    archive_path: Path,
    stage_dir: Path,
    interrupt_after_members: Optional[int] = None,
) -> int:
    """
    Verify integrity and extract .zip or .tar* archive strictly into an isolated staging directory.
    Returns extracted file count; raises ArchiveImportError on corruption, unsafe paths, or interruption.
    """
    lower_name = archive_path.name.lower()
    extracted_count = 0

    if lower_name.endswith(".zip"):
        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                bad_member = zf.testzip()
                if bad_member is not None:
                    raise ArchiveImportError(f"CRC integrity check failed on archive member '{bad_member}'.")
                members = zf.infolist()
                for idx, info in enumerate(members):
                    if interrupt_after_members is not None and idx >= interrupt_after_members:
                        raise ArchiveImportError(
                            f"Interrupted archive extraction after {idx} member(s)."
                        )
                    target = _is_safe_member_path(stage_dir, info.filename)
                    if info.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info, "r") as src, open(target, "wb") as dst:
                        shutil.copyfileobj(src, dst, length=1024 * 1024)
                    extracted_count += 1
            return extracted_count
        except (zipfile.BadZipFile, EOFError, zlib.error, RuntimeError, OSError) as exc:
            raise ArchiveImportError(f"ZIP archive validation/extraction failed: {exc}") from exc

    if lower_name.endswith((".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")):
        try:
            with tarfile.open(archive_path, "r:*") as tf:
                members = tf.getmembers()
                for idx, member in enumerate(members):
                    if interrupt_after_members is not None and idx >= interrupt_after_members:
                        raise ArchiveImportError(
                            f"Interrupted tar extraction after {idx} member(s)."
                        )
                    if member.issym() or member.islnk():
                        raise ArchiveImportError(
                            f"Unsafe symlink/hardlink archive member rejected: '{member.name}'"
                        )
                    target = _is_safe_member_path(stage_dir, member.name)
                    if member.isdir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    if member.isfile():
                        file_obj = tf.extractfile(member)
                        if file_obj is None:
                            raise ArchiveImportError(f"Failed to read tar member payload '{member.name}'.")
                        target.parent.mkdir(parents=True, exist_ok=True)
                        with file_obj, open(target, "wb") as dst:
                            shutil.copyfileobj(file_obj, dst, length=1024 * 1024)
                        extracted_count += 1
            return extracted_count
        except (tarfile.TarError, EOFError, OSError) as exc:
            raise ArchiveImportError(f"TAR archive validation/extraction failed: {exc}") from exc

    raise ArchiveImportError(f"Unsupported archive format for '{archive_path.name}'. Supported: .zip, .tar, .tar.gz, .tgz.")


def _promote_stage_to_raw(stage_dir: Path, raw_dir: Path, allow_overwrite: bool) -> None:
    """Move validated staged files into raw/<dataset>/ without leaving partial leftovers."""
    for item in sorted(stage_dir.rglob("*")):
        rel = item.relative_to(stage_dir)
        dest = (raw_dir / rel).resolve()
        if item.is_dir():
            dest.mkdir(parents=True, exist_ok=True)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and not allow_overwrite:
            raise ArchiveImportError(f"Overwrite blocked: '{dest}' already exists.")
        shutil.move(str(item), str(dest))


def import_dataset_archive(
    dataset_name: str,
    archive_source_path: Path,
    dirs: DatasetDirectories,
    source_url: Optional[str] = None,
    expected_sha256: Optional[str] = None,
    allow_overwrite: bool = False,
    min_free_bytes_multiplier: float = 2.5,
    interrupt_after_members: Optional[int] = None,
) -> ArchiveImportRecord:
    """
    Validate, preserve, and extract a legitimately acquired dataset archive into DATASET_ROOT/raw/<dataset>/.
    Never overwrites existing archives/raw files unless allow_overwrite=True, cleans up temporary staging
    dirs on interrupted/corrupt imports, and logs every attempt to manifests/<dataset>_acquisition_log.jsonl.
    """
    ds = dataset_name.strip().lower()
    now_utc = datetime.now(timezone.utc).isoformat()
    reg_map = {r.dataset_key: r for r in VERIFIED_DATASET_REGISTRY}
    resolved_url = source_url or (reg_map[ds].official_source_url if ds in reg_map else "local_authorized_import")

    src_path = Path(archive_source_path)
    archives_dir = dirs.archives_by_dataset.get(ds, dirs.archives / ds)
    raw_dir = dirs.raw_by_dataset.get(ds, dirs.raw / ds)
    archives_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)

    # 1. Missing archive check
    if not src_path.is_file():
        rec = ArchiveImportRecord(
            dataset_name=ds,
            source_url=resolved_url,
            acquired_at_utc=now_utc,
            source_archive_input=str(src_path),
            archive_filename=src_path.name,
            preserved_archive_path=None,
            archive_sha256=None,
            archive_size_bytes=None,
            extracted_files_count=0,
            status="missing_archive",
            error_detail=f"Archive file not found at '{src_path}'.",
        )
        _append_acquisition_log(dirs.manifests, rec)
        return rec

    archive_size = src_path.stat().st_size
    archive_sha = compute_file_sha256(src_path)

    # 2. Checksum verification if caller provided expected digest
    if expected_sha256 and archive_sha.lower() != expected_sha256.strip().lower():
        rec = ArchiveImportRecord(
            dataset_name=ds,
            source_url=resolved_url,
            acquired_at_utc=now_utc,
            source_archive_input=str(src_path),
            archive_filename=src_path.name,
            preserved_archive_path=None,
            archive_sha256=archive_sha,
            archive_size_bytes=archive_size,
            extracted_files_count=0,
            status="checksum_mismatch",
            error_detail=f"Expected SHA-256 '{expected_sha256}', computed '{archive_sha}'.",
        )
        _append_acquisition_log(dirs.manifests, rec)
        return rec

    # 3. Free disk space check
    required_free = int(archive_size * min_free_bytes_multiplier)
    disk_free = shutil.disk_usage(dirs.root).free
    if disk_free < required_free:
        rec = ArchiveImportRecord(
            dataset_name=ds,
            source_url=resolved_url,
            acquired_at_utc=now_utc,
            source_archive_input=str(src_path),
            archive_filename=src_path.name,
            preserved_archive_path=None,
            archive_sha256=archive_sha,
            archive_size_bytes=archive_size,
            extracted_files_count=0,
            status="insufficient_disk_space",
            error_detail=f"Free disk space ({disk_free} bytes) below required threshold ({required_free} bytes).",
        )
        _append_acquisition_log(dirs.manifests, rec)
        return rec

    # 4. Overwrite guard on both archive store and raw directory
    dest_archive = (archives_dir / src_path.name).resolve()
    existing_raw_files = _count_files(raw_dir)
    if not allow_overwrite and (existing_raw_files > 0 or (dest_archive.exists() and src_path.resolve() != dest_archive)):
        rec = ArchiveImportRecord(
            dataset_name=ds,
            source_url=resolved_url,
            acquired_at_utc=now_utc,
            source_archive_input=str(src_path),
            archive_filename=src_path.name,
            preserved_archive_path=str(dest_archive) if dest_archive.exists() else None,
            archive_sha256=archive_sha,
            archive_size_bytes=archive_size,
            extracted_files_count=0,
            status="overwrite_blocked",
            error_detail=(
                f"Existing data found in '{raw_dir}' ({existing_raw_files} files) or '{dest_archive}'. "
                "Pass allow_overwrite=True intentionally to overwrite."
            ),
        )
        _append_acquisition_log(dirs.manifests, rec)
        return rec

    # 5. Stage archive validation & extraction before touching raw/<dataset>/
    stage_dir = dirs.temporary / f"stage_{ds}_{uuid.uuid4().hex[:8]}"
    stage_dir.mkdir(parents=True, exist_ok=True)
    try:
        extracted_count = _extract_archive_to_stage(
            archive_path=src_path,
            stage_dir=stage_dir,
            interrupt_after_members=interrupt_after_members,
        )
        if extracted_count == 0:
            raise ArchiveImportError("Archive validated cleanly but contained zero regular files.")

        # Preserve original archive untouched in archives/<dataset>/
        if src_path.resolve() != dest_archive:
            temp_archive = dirs.temporary / f"arch_{uuid.uuid4().hex[:8]}_{src_path.name}"
            shutil.copy2(str(src_path), str(temp_archive))
            shutil.move(str(temp_archive), str(dest_archive))

        _promote_stage_to_raw(stage_dir, raw_dir, allow_overwrite=allow_overwrite)

        rec = ArchiveImportRecord(
            dataset_name=ds,
            source_url=resolved_url,
            acquired_at_utc=now_utc,
            source_archive_input=str(src_path),
            archive_filename=src_path.name,
            preserved_archive_path=str(dest_archive),
            archive_sha256=archive_sha,
            archive_size_bytes=archive_size,
            extracted_files_count=extracted_count,
            status="imported",
            error_detail=None,
        )
        _append_acquisition_log(dirs.manifests, rec)
        return rec
    except ArchiveImportError as exc:
        failure_status = "interrupted_import" if "Interrupted" in str(exc) else "corrupt_archive"
        rec = ArchiveImportRecord(
            dataset_name=ds,
            source_url=resolved_url,
            acquired_at_utc=now_utc,
            source_archive_input=str(src_path),
            archive_filename=src_path.name,
            preserved_archive_path=None,
            archive_sha256=archive_sha,
            archive_size_bytes=archive_size,
            extracted_files_count=0,
            status=failure_status,
            error_detail=str(exc),
        )
        _append_acquisition_log(dirs.manifests, rec)
        return rec
    finally:
        # Guarantee interrupted/incomplete staging files never linger
        shutil.rmtree(stage_dir, ignore_errors=True)


def verify_raw_checksums_unchanged(raw_dir: Path, manifest_jsonl_path: Path) -> Dict[str, Any]:
    """Verify every accepted raw image on disk still matches its recorded manifest SHA-256."""
    if not manifest_jsonl_path.is_file():
        return {
            "manifest_exists": False,
            "checked_files": 0,
            "mismatches": [],
            "missing_files": [],
            "all_unchanged": True,
        }

    records = read_manifest_jsonl(manifest_jsonl_path)
    accepted = [r for r in records if r.validation_status == "accepted" and r.sha256_checksum]
    mismatches: List[str] = []
    missing_files: List[str] = []

    for r in accepted:
        target = (raw_dir / r.relative_path).resolve()
        if not target.is_file():
            missing_files.append(r.relative_path)
            continue
        current_sha = compute_file_sha256(target)
        if current_sha != r.sha256_checksum:
            mismatches.append(r.relative_path)

    return {
        "manifest_exists": True,
        "checked_files": len(accepted),
        "mismatches": mismatches,
        "missing_files": missing_files,
        "all_unchanged": not mismatches and not missing_files,
    }


def check_dataset_acquisition_readiness(dirs: DatasetDirectories) -> Dict[str, Any]:
    """
    Inspect host disk headroom, credentials presence, preserved archives, raw files, and manifests
    to report factual acquisition readiness per dataset without ever fabricating downloads.
    """
    usage = shutil.disk_usage(dirs.root)
    kaggle_creds = check_kaggle_credentials_present()
    statuses: List[Dict[str, Any]] = []

    for meta in VERIFIED_DATASET_REGISTRY:
        ds = meta.dataset_key
        arch_dir = dirs.archives_by_dataset.get(ds, dirs.archives / ds)
        raw_dir = dirs.raw_by_dataset.get(ds, dirs.raw / ds)
        archive_files = sorted([p.name for p in arch_dir.iterdir() if p.is_file()]) if arch_dir.is_dir() else []
        raw_count = _count_files(raw_dir)
        manifest_path = dirs.manifests / f"{ds}_manifest.jsonl"
        inspected_count = len(read_manifest_jsonl(manifest_path)) if manifest_path.is_file() else 0

        if raw_count > 0 and inspected_count > 0:
            phase6_status = "extracted_and_inspected"
        elif raw_count > 0:
            phase6_status = "extracted_pending_inspection"
        elif archive_files:
            phase6_status = "archive_present_not_extracted"
        else:
            phase6_status = "awaiting_authorization"

        statuses.append(
            {
                "dataset_key": ds,
                "display_name": meta.display_name,
                "official_source_url": meta.official_source_url,
                "commercial_use_status": meta.commercial_use_status,
                "registration_or_application_required": meta.registration_or_application_required,
                "phase6_status": phase6_status,
                "preserved_archives": archive_files,
                "raw_files_on_disk": raw_count,
                "inspected_manifest_entries": inspected_count,
                "raw_target_directory": str(raw_dir),
                "archives_target_directory": str(arch_dir),
                "manual_acquisition_steps": meta.legitimate_acquisition_steps,
            }
        )

    return {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_root": str(dirs.root),
        "disk_free_gb": round(usage.free / (1024**3), 2),
        "disk_total_gb": round(usage.total / (1024**3), 2),
        "kaggle_credentials": kaggle_creds,
        "datasets": statuses,
    }
