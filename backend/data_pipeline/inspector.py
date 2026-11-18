import hashlib
import io
import os
import warnings
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import pandas as pd
from PIL import Image, ImageFile, UnidentifiedImageError

from data_pipeline.label_mapping import map_dr_label
from data_pipeline.manifest import (
    ManifestRecord,
    write_manifest_csv,
    write_manifest_jsonl,
)

# Reject truncated or corrupted image payloads loudly
ImageFile.LOAD_TRUNCATED_IMAGES = False

SUPPORTED_EXTENSIONS_TO_FORMATS = {
    ".jpg": ("JPEG", "image/jpeg"),
    ".jpeg": ("JPEG", "image/jpeg"),
    ".png": ("PNG", "image/png"),
    ".tif": ("TIFF", "image/tiff"),
    ".tiff": ("TIFF", "image/tiff"),
    ".bmp": ("BMP", "image/bmp"),
    ".gif": ("GIF", "image/gif"),
}


@dataclass
class DatasetInputItem:
    relative_path: str
    raw_label: Optional[str] = None
    task_type: str = "dr_grading"  # 'dr_grading', 'lesion_segmentation', 'vessel_segmentation'
    patient_identifier: Optional[str] = None
    patient_id_limitation_note: str = "Patient identifiers not provided by dataset publisher."
    annotation_availability: str = "image_level_grade_only"
    annotation_relative_paths: List[str] = field(default_factory=list)
    gradable_flag: Optional[str] = None


@dataclass
class InspectionSummary:
    dataset_name: str
    inspected_at: str
    total_entries_inspected: int
    accepted_count: int
    rejected_count: int
    duplicate_exact_count: int
    near_duplicate_candidate_count: int
    missing_image_count: int
    missing_label_count: int
    invalid_label_count: int
    manifest_csv_path: str
    manifest_jsonl_path: str
    rejected_csv_path: str


def compute_dhash_hex(image_bgr_or_gray: np.ndarray) -> str:
    """
    Compute 64-bit perceptual difference hash (dHash) using OpenCV and NumPy
    for near-duplicate flagging (human inspection only; never auto-deleted).
    """
    if image_bgr_or_gray.ndim == 3:
        if image_bgr_or_gray.shape[2] == 4:
            gray = cv2.cvtColor(image_bgr_or_gray, cv2.COLOR_BGRA2GRAY)
        else:
            gray = cv2.cvtColor(image_bgr_or_gray, cv2.COLOR_BGR2GRAY)
    else:
        gray = image_bgr_or_gray

    resized = cv2.resize(gray, (9, 8), interpolation=cv2.INTER_AREA)
    diff = resized[:, 1:] > resized[:, :-1]
    bits = diff.flatten()
    val = 0
    for bit in bits:
        val = (val << 1) | int(bool(bit))
    return f"{val:016x}"


def _hamming_distance_hex(h1: str, h2: str) -> int:
    return bin(int(h1, 16) ^ int(h2, 16)).count("1")


class DatasetInspector:
    """
    Reproducible dataset inspection and validation pipeline using Pillow, OpenCV, NumPy, and Pandas.
    Never alters or deletes any file in raw dataset directories.
    """

    def __init__(
        self,
        min_dimension: int = 32,
        max_pixels: int = 80_000_000,
        near_duplicate_threshold: int = 4,
    ) -> None:
        self.min_dimension = min_dimension
        self.max_pixels = max_pixels
        self.near_duplicate_threshold = near_duplicate_threshold

    def _validate_single_image_file(
        self,
        file_path: Path,
        expected_size: Optional[Tuple[int, int]] = None,
    ) -> Tuple[Optional[dict], Optional[str]]:
        """
        Inspect an individual image file on disk without altering source bytes.
        Returns (metadata_dict, error_reason).
        """
        if not file_path.exists() or not file_path.is_file():
            return None, "Referenced image file does not exist on disk."

        if not os.access(file_path, os.R_OK):
            return None, "Image file is not readable due to filesystem permissions."

        ext = file_path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS_TO_FORMATS:
            return None, f"Unsupported image file extension '{ext}'."

        try:
            file_size = file_path.stat().st_size
            if file_size == 0:
                return None, "Empty file (0 bytes)."

            with open(file_path, "rb") as f:
                raw_bytes = f.read()
        except OSError as exc:
            return None, f"Failed to read file bytes cleanly: {exc.__class__.__name__}"

        if len(raw_bytes) == 0:
            return None, "Empty file (0 bytes)."

        sha256_hex = hashlib.sha256(raw_bytes).hexdigest()
        expected_pil_format, media_type = SUPPORTED_EXTENSIONS_TO_FORMATS[ext]

        previous_max_pixels = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = self.max_pixels

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)

                # First pass: verify structural headers
                with Image.open(io.BytesIO(raw_bytes)) as img:
                    pil_fmt = img.format
                    if pil_fmt != expected_pil_format:
                        return None, (
                            f"Format mismatch: extension '{ext}' expects {expected_pil_format}, "
                            f"but file decoded as {pil_fmt}."
                        )
                    w, h = img.size
                    if w * h > self.max_pixels:
                        return None, "Image exceeds safety maximum pixel count."
                    img.verify()

                # Second pass: force complete scanline load to detect truncation/corruption
                with Image.open(io.BytesIO(raw_bytes)) as decoded_img:
                    decoded_img.load()
                    width, height = decoded_img.size
                    mode = decoded_img.mode
                    # Convert PIL image cleanly to NumPy/OpenCV buffer if needed for channels & dHash
                    if pil_fmt == "GIF":
                        arr_rgb = np.array(decoded_img.convert("RGB"))
                        cv_img = cv2.cvtColor(arr_rgb, cv2.COLOR_RGB2BGR)
                        channels = 1 if mode in ("1", "L", "P") else len(decoded_img.getbands())
                    else:
                        cv_buf = np.frombuffer(raw_bytes, dtype=np.uint8)
                        cv_img = cv2.imdecode(cv_buf, cv2.IMREAD_UNCHANGED)
                        if cv_img is None:
                            return None, "OpenCV failed to decode image pixel matrix."
                        channels = 1 if cv_img.ndim == 2 else int(cv_img.shape[2])

        except (Image.DecompressionBombError, Image.DecompressionBombWarning):
            return None, "Image rejected by decompression-bomb pixel protection."
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            return None, f"Corrupt or truncated image payload ({exc.__class__.__name__})."
        finally:
            Image.MAX_IMAGE_PIXELS = previous_max_pixels

        if width < self.min_dimension or height < self.min_dimension:
            return None, (
                f"Image dimensions ({width}x{height}) below minimum supported "
                f"{self.min_dimension}x{self.min_dimension} threshold."
            )

        if expected_size is not None and (width, height) != expected_size:
            return None, (
                f"Dimension mismatch: expected {expected_size[0]}x{expected_size[1]}, "
                f"found {width}x{height}."
            )

        dhash_hex = compute_dhash_hex(cv_img)

        return {
            "file_size_bytes": file_size,
            "width": int(width),
            "height": int(height),
            "channels": int(channels),
            "detected_media_type": media_type,
            "sha256_checksum": sha256_hex,
            "perceptual_hash": dhash_hex,
        }, None

    def inspect_dataset(
        self,
        dataset_name: str,
        raw_dataset_dir: Path,
        items: List[DatasetInputItem],
        manifests_dir: Path,
        rejected_dir: Path,
        require_valid_label: bool = True,
        fixed_timestamp: Optional[str] = None,
    ) -> Tuple[List[ManifestRecord], InspectionSummary]:
        """
        Validate every entry in deterministic order, write reproducible CSV + JSONL manifests
        and rejection logs, and compute exact validation statistics via Pandas.
        """
        now_iso = fixed_timestamp or datetime.now(timezone.utc).isoformat()
        seen_paths: set = set()
        seen_sha256: Dict[str, str] = {}
        accepted_phashes: List[Tuple[str, str]] = []  # (relative_path, dhash_hex)
        manifest_records: List[ManifestRecord] = []

        # Sort input items deterministically before deduplication so first occurrence is 100% reproducible
        ordered_items = sorted(items, key=lambda x: x.relative_path)

        for item in ordered_items:
            rel_norm = item.relative_path.replace("\\", "/").lstrip("/")
            file_path = (raw_dataset_dir / rel_norm).resolve()
            orig_name = Path(rel_norm).name
            ext = Path(rel_norm).suffix.lower()

            # Ensure label mapping runs cleanly for every row
            mapping = map_dr_label(
                dataset_name=dataset_name,
                raw_label=item.raw_label,
                task_type=item.task_type,
                gradable_flag=item.gradable_flag,
            )

            # Guard path escape outside raw_dataset_dir
            try:
                file_path.relative_to(raw_dataset_dir.resolve())
            except ValueError:
                manifest_records.append(
                    ManifestRecord(
                        dataset_name=dataset_name,
                        original_filename=orig_name,
                        relative_path=rel_norm,
                        file_extension=ext,
                        detected_media_type=None,
                        file_size_bytes=None,
                        width=None,
                        height=None,
                        channels=None,
                        sha256_checksum=None,
                        perceptual_hash=None,
                        raw_label=mapping.raw_label,
                        standardized_label=mapping.standardized_label,
                        standardized_grade_numeric=mapping.standardized_grade_numeric,
                        label_mapping_status=mapping.mapping_status,
                        label_mapping_rationale=mapping.mapping_rationale,
                        annotation_availability=item.annotation_availability,
                        patient_identifier=item.patient_identifier,
                        patient_id_limitation_note=item.patient_id_limitation_note,
                        import_timestamp=now_iso,
                        validation_status="rejected",
                        rejection_reason="Path traversal attempt outside raw dataset root.",
                    )
                )
                continue

            # 1. Check duplicate manifest entry collision
            if rel_norm in seen_paths:
                manifest_records.append(
                    ManifestRecord(
                        dataset_name=dataset_name,
                        original_filename=orig_name,
                        relative_path=rel_norm,
                        file_extension=ext,
                        detected_media_type=None,
                        file_size_bytes=None,
                        width=None,
                        height=None,
                        channels=None,
                        sha256_checksum=None,
                        perceptual_hash=None,
                        raw_label=mapping.raw_label,
                        standardized_label=mapping.standardized_label,
                        standardized_grade_numeric=mapping.standardized_grade_numeric,
                        label_mapping_status=mapping.mapping_status,
                        label_mapping_rationale=mapping.mapping_rationale,
                        annotation_availability=item.annotation_availability,
                        patient_identifier=item.patient_identifier,
                        patient_id_limitation_note=item.patient_id_limitation_note,
                        import_timestamp=now_iso,
                        validation_status="rejected",
                        rejection_reason=f"Duplicate manifest entry / filename collision for '{rel_norm}'.",
                    )
                )
                continue
            seen_paths.add(rel_norm)

            # 2. Validate file existence & image payload decoding
            if not file_path.exists():
                manifest_records.append(
                    ManifestRecord(
                        dataset_name=dataset_name,
                        original_filename=orig_name,
                        relative_path=rel_norm,
                        file_extension=ext,
                        detected_media_type=None,
                        file_size_bytes=None,
                        width=None,
                        height=None,
                        channels=None,
                        sha256_checksum=None,
                        perceptual_hash=None,
                        raw_label=mapping.raw_label,
                        standardized_label=mapping.standardized_label,
                        standardized_grade_numeric=mapping.standardized_grade_numeric,
                        label_mapping_status=mapping.mapping_status,
                        label_mapping_rationale=mapping.mapping_rationale,
                        annotation_availability=item.annotation_availability,
                        patient_identifier=item.patient_identifier,
                        patient_id_limitation_note=item.patient_id_limitation_note,
                        import_timestamp=now_iso,
                        validation_status="missing_image",
                        rejection_reason="Referenced image file missing from disk.",
                    )
                )
                continue

            img_meta, img_err = self._validate_single_image_file(file_path)
            if img_err or img_meta is None:
                manifest_records.append(
                    ManifestRecord(
                        dataset_name=dataset_name,
                        original_filename=orig_name,
                        relative_path=rel_norm,
                        file_extension=ext,
                        detected_media_type=None,
                        file_size_bytes=file_path.stat().st_size if file_path.exists() else None,
                        width=None,
                        height=None,
                        channels=None,
                        sha256_checksum=None,
                        perceptual_hash=None,
                        raw_label=mapping.raw_label,
                        standardized_label=mapping.standardized_label,
                        standardized_grade_numeric=mapping.standardized_grade_numeric,
                        label_mapping_status=mapping.mapping_status,
                        label_mapping_rationale=mapping.mapping_rationale,
                        annotation_availability=item.annotation_availability,
                        patient_identifier=item.patient_identifier,
                        patient_id_limitation_note=item.patient_id_limitation_note,
                        import_timestamp=now_iso,
                        validation_status="rejected",
                        rejection_reason=img_err or "Invalid image file.",
                    )
                )
                continue

            # 3. Verify annotation masks (if segmentation masks attached) match dimensions cleanly
            mask_error: Optional[str] = None
            for ann_rel in item.annotation_relative_paths:
                ann_path = (raw_dataset_dir / ann_rel.replace("\\", "/").lstrip("/")).resolve()
                _, ann_err = self._validate_single_image_file(
                    ann_path,
                    expected_size=(img_meta["width"], img_meta["height"]),
                )
                if ann_err:
                    mask_error = f"Annotation mask '{ann_rel}' invalid: {ann_err}"
                    break

            if mask_error:
                manifest_records.append(
                    ManifestRecord(
                        dataset_name=dataset_name,
                        original_filename=orig_name,
                        relative_path=rel_norm,
                        file_extension=ext,
                        detected_media_type=img_meta["detected_media_type"],
                        file_size_bytes=img_meta["file_size_bytes"],
                        width=img_meta["width"],
                        height=img_meta["height"],
                        channels=img_meta["channels"],
                        sha256_checksum=img_meta["sha256_checksum"],
                        perceptual_hash=img_meta["perceptual_hash"],
                        raw_label=mapping.raw_label,
                        standardized_label=mapping.standardized_label,
                        standardized_grade_numeric=mapping.standardized_grade_numeric,
                        label_mapping_status=mapping.mapping_status,
                        label_mapping_rationale=mapping.mapping_rationale,
                        annotation_availability=item.annotation_availability,
                        patient_identifier=item.patient_identifier,
                        patient_id_limitation_note=item.patient_id_limitation_note,
                        import_timestamp=now_iso,
                        validation_status="rejected",
                        rejection_reason=mask_error,
                    )
                )
                continue

            # 4. Exact SHA-256 duplicate detection
            checksum = img_meta["sha256_checksum"]
            if checksum in seen_sha256:
                manifest_records.append(
                    ManifestRecord(
                        dataset_name=dataset_name,
                        original_filename=orig_name,
                        relative_path=rel_norm,
                        file_extension=ext,
                        detected_media_type=img_meta["detected_media_type"],
                        file_size_bytes=img_meta["file_size_bytes"],
                        width=img_meta["width"],
                        height=img_meta["height"],
                        channels=img_meta["channels"],
                        sha256_checksum=checksum,
                        perceptual_hash=img_meta["perceptual_hash"],
                        raw_label=mapping.raw_label,
                        standardized_label=mapping.standardized_label,
                        standardized_grade_numeric=mapping.standardized_grade_numeric,
                        label_mapping_status=mapping.mapping_status,
                        label_mapping_rationale=mapping.mapping_rationale,
                        annotation_availability=item.annotation_availability,
                        patient_identifier=item.patient_identifier,
                        patient_id_limitation_note=item.patient_id_limitation_note,
                        import_timestamp=now_iso,
                        validation_status="duplicate_exact",
                        rejection_reason=f"Exact SHA-256 duplicate of '{seen_sha256[checksum]}'.",
                    )
                )
                continue

            # 5. Label validation (for labeled classification datasets)
            if item.task_type == "dr_grading":
                if mapping.mapping_status == "missing" and require_valid_label:
                    manifest_records.append(
                        ManifestRecord(
                            dataset_name=dataset_name,
                            original_filename=orig_name,
                            relative_path=rel_norm,
                            file_extension=ext,
                            detected_media_type=img_meta["detected_media_type"],
                            file_size_bytes=img_meta["file_size_bytes"],
                            width=img_meta["width"],
                            height=img_meta["height"],
                            channels=img_meta["channels"],
                            sha256_checksum=checksum,
                            perceptual_hash=img_meta["perceptual_hash"],
                            raw_label=mapping.raw_label,
                            standardized_label=None,
                            standardized_grade_numeric=None,
                            label_mapping_status=mapping.mapping_status,
                            label_mapping_rationale=mapping.mapping_rationale,
                            annotation_availability=item.annotation_availability,
                            patient_identifier=item.patient_identifier,
                            patient_id_limitation_note=item.patient_id_limitation_note,
                            import_timestamp=now_iso,
                            validation_status="rejected",
                            rejection_reason="Missing DR severity label.",
                        )
                    )
                    continue
                if mapping.mapping_status == "unresolved":
                    manifest_records.append(
                        ManifestRecord(
                            dataset_name=dataset_name,
                            original_filename=orig_name,
                            relative_path=rel_norm,
                            file_extension=ext,
                            detected_media_type=img_meta["detected_media_type"],
                            file_size_bytes=img_meta["file_size_bytes"],
                            width=img_meta["width"],
                            height=img_meta["height"],
                            channels=img_meta["channels"],
                            sha256_checksum=checksum,
                            perceptual_hash=img_meta["perceptual_hash"],
                            raw_label=mapping.raw_label,
                            standardized_label=None,
                            standardized_grade_numeric=None,
                            label_mapping_status=mapping.mapping_status,
                            label_mapping_rationale=mapping.mapping_rationale,
                            annotation_availability=item.annotation_availability,
                            patient_identifier=item.patient_identifier,
                            patient_id_limitation_note=item.patient_id_limitation_note,
                            import_timestamp=now_iso,
                            validation_status="rejected",
                            rejection_reason=f"Invalid or unresolved DR label: '{mapping.raw_label}'.",
                        )
                    )
                    continue

            seen_sha256[checksum] = rel_norm

            # 6. Near-duplicate perceptual check (flag ONLY for review; NEVER auto-drop!)
            is_near_dup = False
            near_dup_target: Optional[str] = None
            cur_dhash = img_meta["perceptual_hash"]
            for prev_path, prev_dhash in accepted_phashes:
                if _hamming_distance_hex(cur_dhash, prev_dhash) <= self.near_duplicate_threshold:
                    is_near_dup = True
                    near_dup_target = prev_path
                    break
            accepted_phashes.append((rel_norm, cur_dhash))

            manifest_records.append(
                ManifestRecord(
                    dataset_name=dataset_name,
                    original_filename=orig_name,
                    relative_path=rel_norm,
                    file_extension=ext,
                    detected_media_type=img_meta["detected_media_type"],
                    file_size_bytes=img_meta["file_size_bytes"],
                    width=img_meta["width"],
                    height=img_meta["height"],
                    channels=img_meta["channels"],
                    sha256_checksum=checksum,
                    perceptual_hash=cur_dhash,
                    raw_label=mapping.raw_label,
                    standardized_label=mapping.standardized_label,
                    standardized_grade_numeric=mapping.standardized_grade_numeric,
                    label_mapping_status=mapping.mapping_status,
                    label_mapping_rationale=mapping.mapping_rationale,
                    annotation_availability=item.annotation_availability,
                    patient_identifier=item.patient_identifier,
                    patient_id_limitation_note=item.patient_id_limitation_note,
                    import_timestamp=now_iso,
                    validation_status="accepted",
                    rejection_reason=None,
                    is_near_duplicate_candidate=is_near_dup,
                    near_duplicate_of=near_dup_target,
                )
            )

        # Write reproducible CSV & JSONL manifests + separated rejection audit CSV
        manifest_csv = manifests_dir / f"{dataset_name}_manifest.csv"
        manifest_jsonl = manifests_dir / f"{dataset_name}_manifest.jsonl"
        rejected_csv = rejected_dir / f"{dataset_name}_rejected.csv"

        write_manifest_csv(manifest_records, manifest_csv)
        write_manifest_jsonl(manifest_records, manifest_jsonl)

        rejected_records = [r for r in manifest_records if r.validation_status != "accepted"]
        write_manifest_csv(rejected_records, rejected_csv)

        # Aggregate factual statistics via Pandas
        if manifest_records:
            df = pd.DataFrame([r.__dict__ for r in manifest_records])
            accepted_cnt = int((df["validation_status"] == "accepted").sum())
            rejected_cnt = int((df["validation_status"] == "rejected").sum())
            dup_cnt = int((df["validation_status"] == "duplicate_exact").sum())
            missing_img_cnt = int((df["validation_status"] == "missing_image").sum())
            near_dup_cnt = int(df["is_near_duplicate_candidate"].sum())
            missing_lbl_cnt = int((df["label_mapping_status"] == "missing").sum())
            invalid_lbl_cnt = int((df["label_mapping_status"] == "unresolved").sum())
        else:
            accepted_cnt = rejected_cnt = dup_cnt = missing_img_cnt = near_dup_cnt = missing_lbl_cnt = invalid_lbl_cnt = 0

        summary = InspectionSummary(
            dataset_name=dataset_name,
            inspected_at=now_iso,
            total_entries_inspected=len(manifest_records),
            accepted_count=accepted_cnt,
            rejected_count=rejected_cnt,
            duplicate_exact_count=dup_cnt,
            near_duplicate_candidate_count=near_dup_cnt,
            missing_image_count=missing_img_cnt,
            missing_label_count=missing_lbl_cnt,
            invalid_label_count=invalid_lbl_cnt,
            manifest_csv_path=str(manifest_csv),
            manifest_jsonl_path=str(manifest_jsonl),
            rejected_csv_path=str(rejected_csv),
        )
        return manifest_records, summary
