"""Cross-dataset data quality, duplication, leakage, and Phase 6 readiness auditing."""

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from data_pipeline.archive_importer import check_dataset_acquisition_readiness
from data_pipeline.directory_manager import DatasetDirectories
from data_pipeline.inspector import _hamming_distance_hex
from data_pipeline.manifest import ManifestRecord, read_manifest_jsonl
from data_pipeline.registry import VERIFIED_DATASET_REGISTRY


def inspect_cross_dataset_quality(
    dirs: DatasetDirectories,
    near_dup_hamming_threshold: int = 5,
    extra_datasets: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Analyze all locally inspected manifests across datasets for exact SHA-256 overlap,
    near-duplicate perceptual hash collisions, dataset-specific rule adherence,
    and truthful Phase 6 sufficiency for future model development.
    """
    readiness = check_dataset_acquisition_readiness(dirs)
    dataset_keys = [r.dataset_key for r in VERIFIED_DATASET_REGISTRY]
    for extra in extra_datasets or []:
        k = extra.strip().lower()
        if k and k not in dataset_keys:
            dataset_keys.append(k)

    # Also auto-include any other *_manifest.jsonl present in dirs.manifests
    if dirs.manifests.is_dir():
        for mf in sorted(dirs.manifests.glob("*_manifest.jsonl")):
            ds_name = mf.name[: -len("_manifest.jsonl")]
            if ds_name not in dataset_keys:
                dataset_keys.append(ds_name)

    per_dataset: Dict[str, Any] = {}
    accepted_pool: List[ManifestRecord] = []

    datasets_downloaded: List[str] = []
    datasets_extracted: List[str] = []
    datasets_inspected: List[str] = []
    datasets_awaiting_auth: List[str] = []
    datasets_with_issues: List[Dict[str, str]] = []

    reg_map = {r.dataset_key: r for r in VERIFIED_DATASET_REGISTRY}

    for ds in dataset_keys:
        raw_dir = dirs.raw_by_dataset.get(ds, dirs.raw / ds)
        arch_dir = dirs.archives_by_dataset.get(ds, dirs.archives / ds)
        manifest_path = dirs.manifests / f"{ds}_manifest.jsonl"

        raw_files_count = sum(1 for p in raw_dir.rglob("*") if p.is_file()) if raw_dir.is_dir() else 0
        arch_files_count = sum(1 for p in arch_dir.iterdir() if p.is_file()) if arch_dir.is_dir() else 0
        records = read_manifest_jsonl(manifest_path) if manifest_path.is_file() else []

        if arch_files_count > 0 or raw_files_count > 0:
            datasets_downloaded.append(ds)
        if raw_files_count > 0:
            datasets_extracted.append(ds)

        accepted = [r for r in records if r.validation_status == "accepted"]
        rejected = [r for r in records if r.validation_status == "rejected"]
        dup_exact = [r for r in records if r.validation_status == "duplicate_exact"]
        missing_img = [r for r in records if r.validation_status == "missing_image"]
        missing_lbl = [r for r in records if r.label_mapping_status == "missing"]

        if records and raw_files_count > 0:
            datasets_inspected.append(ds)
        elif ds in reg_map and arch_files_count == 0 and raw_files_count == 0:
            datasets_awaiting_auth.append(ds)

        # Label and dimension summaries strictly from real inspected accepted entries
        label_dist: Dict[str, int] = {}
        format_dist: Dict[str, int] = {}
        widths: List[int] = []
        heights: List[int] = []
        patient_ids_present = 0

        for r in accepted:
            lbl_key = r.standardized_label or r.label_mapping_status
            label_dist[lbl_key] = label_dist.get(lbl_key, 0) + 1
            fmt_key = r.detected_media_type or r.file_extension or "unknown"
            format_dist[fmt_key] = format_dist.get(fmt_key, 0) + 1
            if r.width and r.height:
                widths.append(int(r.width))
                heights.append(int(r.height))
            if r.patient_identifier and str(r.patient_identifier).strip():
                patient_ids_present += 1

        dim_summary = (
            {
                "width_min": int(np.min(widths)),
                "width_median": float(np.median(widths)),
                "width_max": int(np.max(widths)),
                "height_min": int(np.min(heights)),
                "height_median": float(np.median(heights)),
                "height_max": int(np.max(heights)),
            }
            if widths and heights
            else {}
        )

        # Evaluate known quality / licensing constraints
        meta = reg_map.get(ds)
        if meta:
            if meta.commercial_use_status in ("prohibited", "restricted_or_requires_clearance", "unclear_noncommercial"):
                datasets_with_issues.append(
                    {
                        "dataset_key": ds,
                        "issue_type": "licensing_or_commercial_restriction",
                        "detail": f"{meta.commercial_use_status}: {meta.license_and_terms}",
                    }
                )
            if not meta.patient_identifiers_available:
                datasets_with_issues.append(
                    {
                        "dataset_key": ds,
                        "issue_type": "missing_patient_identifiers",
                        "detail": "Patient-level split separation cannot be cryptographically/metadata-verified.",
                    }
                )

        per_dataset[ds] = {
            "raw_files_on_disk": raw_files_count,
            "preserved_archives_count": arch_files_count,
            "manifest_entries": len(records),
            "accepted_images": len(accepted),
            "rejected_images": len(rejected),
            "exact_duplicates_within_dataset": len(dup_exact),
            "missing_images": len(missing_img),
            "missing_labels": len(missing_lbl),
            "patient_ids_present_count": patient_ids_present,
            "patient_level_split_verifiable": bool(accepted) and patient_ids_present == len(accepted),
            "label_distribution": label_dist,
            "format_distribution": format_dist,
            "dimension_summary": dim_summary,
        }
        accepted_pool.extend(accepted)

    # Cross-dataset exact SHA-256 overlap check
    sha_to_origins: Dict[str, List[Dict[str, str]]] = {}
    for rec in accepted_pool:
        if not rec.sha256_checksum:
            continue
        sha_to_origins.setdefault(rec.sha256_checksum, []).append(
            {"dataset": rec.dataset_name, "relative_path": rec.relative_path}
        )

    cross_dataset_exact_duplicates: List[Dict[str, Any]] = []
    for sha, occs in sha_to_origins.items():
        distinct_ds = sorted({o["dataset"] for o in occs})
        if len(distinct_ds) >= 2:
            cross_dataset_exact_duplicates.append(
                {
                    "sha256_checksum": sha,
                    "datasets": distinct_ds,
                    "occurrences": occs,
                }
            )

    # Cross-dataset perceptual dHash near-duplicate scan (only pairs across distinct datasets)
    cross_dataset_near_duplicates: List[Dict[str, Any]] = []
    dhash_records = [r for r in accepted_pool if r.perceptual_hash]
    for i in range(len(dhash_records)):
        r1 = dhash_records[i]
        for j in range(i + 1, len(dhash_records)):
            r2 = dhash_records[j]
            if r1.dataset_name == r2.dataset_name:
                continue
            if r1.sha256_checksum == r2.sha256_checksum:
                continue
            dist = _hamming_distance_hex(r1.perceptual_hash, r2.perceptual_hash)  # type: ignore[arg-type]
            if dist <= near_dup_hamming_threshold:
                cross_dataset_near_duplicates.append(
                    {
                        "hamming_distance": dist,
                        "record_a": {"dataset": r1.dataset_name, "relative_path": r1.relative_path},
                        "record_b": {"dataset": r2.dataset_name, "relative_path": r2.relative_path},
                    }
                )

    # Honest Final Gate determination: DRIVE cannot qualify as a 5-class DR training set,
    # and Messidor-2 is non-commercial external eval only.
    dr_dev_ready_count = 0
    for ds_name, stats in per_dataset.items():
        if ds_name == "drive" or ds_name == "messidor2":
            continue
        # Count records that have actual mapped 0..4 DR labels
        mapped_dr = sum(
            cnt
            for lbl, cnt in stats["label_distribution"].items()
            if lbl in ("NO_DR", "MILD_NPDR", "MODERATE_NPDR", "SEVERE_NPDR", "PDR")
        )
        dr_dev_ready_count += mapped_dr

    sufficient = dr_dev_ready_count > 0

    return {
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_root": str(dirs.root),
        "disk_free_gb": readiness["disk_free_gb"],
        "datasets_actually_downloaded": datasets_downloaded,
        "datasets_extracted": datasets_extracted,
        "datasets_inspected": datasets_inspected,
        "datasets_awaiting_authorization": datasets_awaiting_auth,
        "datasets_with_quality_or_licensing_issues": datasets_with_issues,
        "per_dataset_metrics": per_dataset,
        "cross_dataset_exact_duplicates": cross_dataset_exact_duplicates,
        "cross_dataset_near_duplicates": cross_dataset_near_duplicates,
        "dr_development_labeled_images_verified": dr_dev_ready_count,
        "sufficient_for_model_development": sufficient,
        "final_gate_reason": (
            f"Verified {dr_dev_ready_count} locally inspected DR classification images."
            if sufficient
            else "Zero legitimate research DR datasets downloaded/inspected on disk; all 4 target datasets await user authorization and manual/authorized download."
        ),
    }
