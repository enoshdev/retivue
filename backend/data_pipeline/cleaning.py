"""Phase 8 duplicate analysis, label-conflict quarantine, train/test overlap audit, and class imbalance metrics."""

import csv
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from data_pipeline.label_mapping import DR_CANDIDATE_SCHEME
from data_pipeline.manifest import ManifestRecord, read_manifest_jsonl


@dataclass(frozen=True)
class DuplicateGroupRecord:
    sha256_checksum: str
    group_size: int
    filenames: str
    relative_paths: str
    raw_labels: str
    standardized_labels: str
    labels_agree: bool
    disposition: str  # 'retained_representative', 'excluded_consistent_duplicate', 'quarantined_label_conflict'
    retained_relative_path: Optional[str]
    byte_identical_verified: bool
    note: str


@dataclass(frozen=True)
class ConflictQuarantineRecord:
    sha256_checksum: str
    relative_path: str
    original_filename: str
    raw_label: str
    standardized_label: str
    conflicting_labels_in_group: str
    peer_filenames_in_group: str
    byte_identical_verified: bool
    quarantine_reason: str


@dataclass(frozen=True)
class TrainTestOverlapRecord:
    shared_sha256: str
    train_filename: str
    train_relative_path: str
    train_raw_label: str
    train_standardized_label: str
    train_in_conflict_group: bool
    test_filename: str
    test_relative_path: str
    byte_identical_verified: bool
    overlap_note: str


def _verify_group_byte_identical(raw_dir: Path, rel_paths: List[str]) -> bool:
    """Confirm multiple files truly share identical raw bytes on disk without relying solely on cached metadata."""
    if len(rel_paths) < 2:
        return True
    first_path = (raw_dir / rel_paths[0]).resolve()
    if not first_path.is_file():
        return False
    ref_bytes = first_path.read_bytes()
    for rp in rel_paths[1:]:
        p = (raw_dir / rp).resolve()
        if not p.is_file() or p.read_bytes() != ref_bytes:
            return False
    return True


def _compute_class_imbalance_strategies(counts_by_grade: Dict[int, int]) -> Dict[str, Any]:
    """
    Compute configurable class-imbalance mitigation weights for later training phases
    without duplicating images or synthesizing labels.
    """
    total = sum(counts_by_grade.values())
    n_classes = len(DR_CANDIDATE_SCHEME)
    if total == 0:
        return {"total_eligible": 0, "per_class": {}, "strategies": {}}

    per_class: Dict[str, Any] = {}
    inv_freq_weights: Dict[str, float] = {}
    sqrt_inv_weights: Dict[str, float] = {}
    effective_num_weights: Dict[str, float] = {}
    beta = 0.999

    max_count = max(counts_by_grade.values()) if counts_by_grade else 1
    min_count = min(v for v in counts_by_grade.values() if v > 0) if any(counts_by_grade.values()) else 1

    raw_eff = {}
    for grade, name in DR_CANDIDATE_SCHEME.items():
        cnt = counts_by_grade.get(grade, 0)
        pct = round((cnt / total) * 100.0, 2) if total else 0.0
        per_class[name] = {
            "grade": grade,
            "count": cnt,
            "percentage": pct,
        }
        if cnt > 0:
            inv_freq_weights[name] = round(total / (n_classes * cnt), 6)
            sqrt_inv_weights[name] = round((max_count / cnt) ** 0.5, 6)
            eff = (1.0 - (beta**cnt)) / (1.0 - beta)
            raw_eff[name] = 1.0 / eff
        else:
            inv_freq_weights[name] = 0.0
            sqrt_inv_weights[name] = 0.0
            raw_eff[name] = 0.0

    # Normalize effective-number weights so their positive mean is 1.0
    pos_eff = [v for v in raw_eff.values() if v > 0]
    eff_mean = (sum(pos_eff) / len(pos_eff)) if pos_eff else 1.0
    for name, val in raw_eff.items():
        effective_num_weights[name] = round(val / eff_mean, 6) if val > 0 else 0.0

    return {
        "total_eligible": total,
        "majority_to_minority_ratio": round(max_count / min_count, 2) if min_count > 0 else None,
        "per_class": per_class,
        "strategies_for_phase9_evaluation": {
            "inverse_frequency_class_weights": inv_freq_weights,
            "sqrt_inverse_frequency_weights": sqrt_inv_weights,
            "effective_number_weights_beta_0_999": effective_num_weights,
            "weighted_random_sampler": {
                "recommended_for_evaluation": True,
                "note": "Sample probability proportional to inverse class count; preserves original dataset without image duplication.",
            },
            "augmentation_config_candidate": {
                "horizontal_flip": True,
                "vertical_flip": True,
                "rotation_degrees": 180,
                "brightness_contrast_jitter": 0.10,
                "geometric_warp_or_synthetic_lesions": False,
            },
        },
    }


def analyze_and_clean_aptos_dataset(
    raw_dataset_dir: Path,
    manifest_jsonl_path: Path,
    reports_dir: Path,
    verify_byte_identity: bool = True,
) -> Dict[str, Any]:
    """
    Reconcile all official APTOS training and test records:
    1. Identify every exact SHA-256 duplicate group within training images.
    2. Quarantine ALL members of any duplicate group with conflicting DR grades (never auto-pick).
    3. Keep deterministically sorted first representative for consistent-label duplicate groups
       and log excluded redundant copies.
    4. Document all exact SHA-256 overlaps between training and official unlabeled test images.
    5. Output machine-readable CSVs and summary metrics without altering raw files.
    """
    reports_dir.mkdir(parents=True, exist_ok=True)
    records: List[ManifestRecord] = read_manifest_jsonl(manifest_jsonl_path)

    train_records = [
        r
        for r in records
        if r.relative_path.replace("\\", "/").startswith("train_images/")
    ]
    test_records = [
        r
        for r in records
        if r.relative_path.replace("\\", "/").startswith("test_images/")
    ]

    # Group ALL decoded train_images by SHA-256 checksum
    train_by_sha: Dict[str, List[ManifestRecord]] = {}
    corrupt_or_missing_train: List[ManifestRecord] = []
    for r in sorted(train_records, key=lambda x: x.relative_path):
        if r.validation_status in ("missing_image",) or not r.sha256_checksum or r.standardized_grade_numeric is None:
            corrupt_or_missing_train.append(r)
            continue
        train_by_sha.setdefault(r.sha256_checksum, []).append(r)

    duplicate_rows: List[DuplicateGroupRecord] = []
    quarantine_rows: List[ConflictQuarantineRecord] = []
    conflict_shas: set = set()
    consistent_dup_excluded_paths: set = set()
    eligible_records: List[ManifestRecord] = []

    raw_class_counts: Dict[int, int] = {g: 0 for g in DR_CANDIDATE_SCHEME}
    for r in train_records:
        if r.standardized_grade_numeric is not None:
            raw_class_counts[r.standardized_grade_numeric] += 1

    consistent_dup_groups_count = 0
    conflicting_dup_groups_count = 0
    consistent_dup_extra_count = 0

    for sha, grp in sorted(train_by_sha.items(), key=lambda kv: kv[1][0].relative_path):
        grp_sorted = sorted(grp, key=lambda x: x.relative_path)
        if len(grp_sorted) == 1:
            eligible_records.append(grp_sorted[0])
            continue

        rel_paths = [r.relative_path for r in grp_sorted]
        fnames = [r.original_filename for r in grp_sorted]
        raw_labels = [str(r.raw_label) for r in grp_sorted]
        std_labels = [str(r.standardized_label) for r in grp_sorted]
        distinct_grades = {r.standardized_grade_numeric for r in grp_sorted}
        labels_agree = len(distinct_grades) == 1
        byte_ok = _verify_group_byte_identical(raw_dataset_dir, rel_paths) if verify_byte_identity else True

        if labels_agree:
            consistent_dup_groups_count += 1
            rep = grp_sorted[0]
            eligible_records.append(rep)
            for extra in grp_sorted[1:]:
                consistent_dup_excluded_paths.add(extra.relative_path)
                consistent_dup_extra_count += 1

            duplicate_rows.append(
                DuplicateGroupRecord(
                    sha256_checksum=sha,
                    group_size=len(grp_sorted),
                    filenames="|".join(fnames),
                    relative_paths="|".join(rel_paths),
                    raw_labels="|".join(raw_labels),
                    standardized_labels="|".join(std_labels),
                    labels_agree=True,
                    disposition="retained_first_excluded_redundant_duplicates",
                    retained_relative_path=rep.relative_path,
                    byte_identical_verified=byte_ok,
                    note=f"Retained {rep.original_filename}; excluded {len(grp_sorted) - 1} byte-identical duplicate(s).",
                )
            )
        else:
            conflicting_dup_groups_count += 1
            conflict_shas.add(sha)
            distinct_str = "|".join(sorted({f"{r.raw_label}:{r.standardized_label}" for r in grp_sorted}))
            duplicate_rows.append(
                DuplicateGroupRecord(
                    sha256_checksum=sha,
                    group_size=len(grp_sorted),
                    filenames="|".join(fnames),
                    relative_paths="|".join(rel_paths),
                    raw_labels="|".join(raw_labels),
                    standardized_labels="|".join(std_labels),
                    labels_agree=False,
                    disposition="quarantined_all_members_label_conflict",
                    retained_relative_path=None,
                    byte_identical_verified=byte_ok,
                    note=f"Conflicting DR labels ({distinct_str}); quarantined ALL {len(grp_sorted)} images.",
                )
            )
            for r in grp_sorted:
                quarantine_rows.append(
                    ConflictQuarantineRecord(
                        sha256_checksum=sha,
                        relative_path=r.relative_path,
                        original_filename=r.original_filename,
                        raw_label=str(r.raw_label),
                        standardized_label=str(r.standardized_label),
                        conflicting_labels_in_group=distinct_str,
                        peer_filenames_in_group="|".join(fnames),
                        byte_identical_verified=byte_ok,
                        quarantine_reason="Byte-identical exact SHA-256 duplicate group has conflicting DR severity grades in train.csv.",
                    )
                )

    # Investigate ALL train vs official unlabeled test exact SHA-256 overlaps
    test_by_sha: Dict[str, List[ManifestRecord]] = {}
    for r in sorted(test_records, key=lambda x: x.relative_path):
        if r.sha256_checksum:
            test_by_sha.setdefault(r.sha256_checksum, []).append(r)

    overlap_rows: List[TrainTestOverlapRecord] = []
    shared_shas = sorted(set(train_by_sha.keys()) & set(test_by_sha.keys()))
    for sha in shared_shas:
        t_trains = sorted(train_by_sha[sha], key=lambda x: x.relative_path)
        t_tests = sorted(test_by_sha[sha], key=lambda x: x.relative_path)
        all_paths = [x.relative_path for x in t_trains] + [x.relative_path for x in t_tests]
        byte_ok = _verify_group_byte_identical(raw_dataset_dir, all_paths) if verify_byte_identity else True
        for tr in t_trains:
            for te in t_tests:
                overlap_rows.append(
                    TrainTestOverlapRecord(
                        shared_sha256=sha,
                        train_filename=tr.original_filename,
                        train_relative_path=tr.relative_path,
                        train_raw_label=str(tr.raw_label),
                        train_standardized_label=str(tr.standardized_label),
                        train_in_conflict_group=sha in conflict_shas,
                        test_filename=te.original_filename,
                        test_relative_path=te.relative_path,
                        byte_identical_verified=byte_ok,
                        overlap_note=(
                            "Official unlabeled test image bytes match training image bytes exactly; "
                            "test image excluded from training/validation, and overlap flags evaluation leakage risk on Kaggle test_images."
                        ),
                    )
                )

    # Export CSV deliverables cleanly
    dup_csv = reports_dir / "phase_8_duplicate_analysis.csv"
    with open(dup_csv, "w", newline="", encoding="utf-8") as f:
        fields = list(DuplicateGroupRecord.__dataclass_fields__.keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in duplicate_rows:
            w.writerow(asdict(row))

    quar_csv = reports_dir / "phase_8_conflict_quarantine.csv"
    with open(quar_csv, "w", newline="", encoding="utf-8") as f:
        fields = list(ConflictQuarantineRecord.__dataclass_fields__.keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in quarantine_rows:
            w.writerow(asdict(row))

    overlap_csv = reports_dir / "phase_8_train_test_overlap.csv"
    with open(overlap_csv, "w", newline="", encoding="utf-8") as f:
        fields = list(TrainTestOverlapRecord.__dataclass_fields__.keys())
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for row in overlap_rows:
            w.writerow(asdict(row))

    eligible_class_counts: Dict[int, int] = {g: 0 for g in DR_CANDIDATE_SCHEME}
    for r in eligible_records:
        if r.standardized_grade_numeric is not None:
            eligible_class_counts[r.standardized_grade_numeric] += 1

    # Count unique eligible records overlapping test_images SHA-256 (for full visibility)
    eligible_overlap_test_count = sum(1 for r in eligible_records if r.sha256_checksum in shared_shas)

    return {
        "analyzed_at_utc": datetime.now(timezone.utc).isoformat(),
        "raw_train_total": len(train_records),
        "raw_test_total": len(test_records),
        "corrupt_or_missing_train": len(corrupt_or_missing_train),
        "consistent_duplicate_groups": consistent_dup_groups_count,
        "consistent_duplicates_excluded": consistent_dup_extra_count,
        "conflicting_duplicate_groups": conflicting_dup_groups_count,
        "conflicting_images_quarantined": len(quarantine_rows),
        "eligible_labeled_train_images": len(eligible_records),
        "eligible_overlapping_official_test_sha256": eligible_overlap_test_count,
        "train_test_shared_unique_sha256_count": len(shared_shas),
        "train_test_overlap_pairs_count": len(overlap_rows),
        "raw_class_counts": {DR_CANDIDATE_SCHEME[g]: c for g, c in raw_class_counts.items()},
        "eligible_class_counts": {DR_CANDIDATE_SCHEME[g]: c for g, c in eligible_class_counts.items()},
        "imbalance_analysis": _compute_class_imbalance_strategies(eligible_class_counts),
        "eligible_records": eligible_records,
        "shared_test_shas": sorted(shared_shas),
        "conflict_shas": sorted(conflict_shas),
        "outputs": {
            "duplicate_analysis_csv": str(dup_csv),
            "conflict_quarantine_csv": str(quar_csv),
            "train_test_overlap_csv": str(overlap_csv),
        },
    }


def _compute_train_channel_stats(
    processed_dir: Path,
    train_proc_rel_paths: List[str],
) -> Dict[str, Any]:
    """Compute exact [0, 1]-scaled per-channel RGB mean and std strictly across the train split."""
    if not train_proc_rel_paths:
        return {"sample_count": 0, "rgb_mean_0_1": [], "rgb_std_0_1": []}

    import numpy as np
    from PIL import Image

    channel_sum = np.zeros(3, dtype=np.float64)
    channel_sq_sum = np.zeros(3, dtype=np.float64)
    total_pixels = 0

    for rel in train_proc_rel_paths:
        p = (processed_dir / rel).resolve()
        if not p.is_file():
            continue
        with Image.open(p) as im:
            arr = np.asarray(im.convert("RGB"), dtype=np.float64) / 255.0
        n_pix = arr.shape[0] * arr.shape[1]
        channel_sum += arr.reshape(-1, 3).sum(axis=0)
        channel_sq_sum += (arr.reshape(-1, 3) ** 2).sum(axis=0)
        total_pixels += n_pix

    if total_pixels == 0:
        return {"sample_count": 0, "rgb_mean_0_1": [], "rgb_std_0_1": []}

    mean = channel_sum / total_pixels
    var = np.maximum(0.0, (channel_sq_sum / total_pixels) - (mean**2))
    std = np.sqrt(var)
    return {
        "sample_count": len(train_proc_rel_paths),
        "total_pixels_per_channel": int(total_pixels),
        "rgb_mean_0_1": [round(float(x), 6) for x in mean],
        "rgb_std_0_1": [round(float(x), 6) for x in std],
        "computed_on_split_only": "train",
    }


def run_phase8_aptos_pipeline(
    dirs: Any,
    target_size: int = 512,
    clahe_applied: bool = False,
    seed: int = 42,
    train_ratio: float = 0.80,
    val_ratio: float = 0.20,
    verify_byte_identity: bool = True,
    exclude_train_overlapping_test: bool = False,
) -> Dict[str, Any]:
    """
    Execute the complete Phase 8 cleaning, FOV-cropping preprocessing, quality flagging,
    train/val stratified group split, empirical train-split normalization stats,
    and chart generation workflow on APTOS 2019 using existing Phase 5/6 infrastructure.
    """
    from data_pipeline.archive_importer import verify_raw_checksums_unchanged
    from data_pipeline.audit_reporter import generate_phase8_cleaning_charts
    from data_pipeline.preprocessor import DatasetPreprocessor, PreprocessingConfig
    from data_pipeline.split_planner import plan_stratified_group_train_val_split

    raw_aptos = dirs.raw_by_dataset["aptos"]
    manifest_jsonl = dirs.manifests / "aptos_manifest.jsonl"
    processed_aptos = dirs.processed / "aptos"

    clean_res = analyze_and_clean_aptos_dataset(
        raw_dataset_dir=raw_aptos,
        manifest_jsonl_path=manifest_jsonl,
        reports_dir=dirs.reports,
        verify_byte_identity=verify_byte_identity,
    )

    candidate_records: List[ManifestRecord] = clean_res["eligible_records"]
    shared_shas = set(clean_res["shared_test_shas"])
    if exclude_train_overlapping_test:
        candidate_records = [r for r in candidate_records if r.sha256_checksum not in shared_shas]

    config = PreprocessingConfig.phase8_aptos_preset(
        target_size=(target_size, target_size),
        clahe_applied=clahe_applied,
    )
    preprocessor = DatasetPreprocessor(config=config)
    prep_records, prep_log_path = preprocessor.run(
        dataset_name="aptos",
        records=candidate_records,
        raw_dataset_dir=raw_aptos,
        processed_dataset_dir=processed_aptos,
        manifests_dir=dirs.manifests,
        log_filename="aptos_phase8_preprocessing_log.jsonl",
    )

    processed_by_source: Dict[str, str] = {}
    flagged_rows: List[Dict[str, Any]] = []
    original_dims = []
    processed_dims = []

    for pr in prep_records:
        if pr.original_width and pr.original_height:
            original_dims.append((pr.original_width, pr.original_height))
        if pr.status == "processed" and pr.processed_relative_path:
            processed_by_source[pr.source_relative_path] = pr.processed_relative_path
            processed_dims.append((pr.processed_width, pr.processed_height))
        else:
            flagged_rows.append(asdict(pr))

    flagged_csv = dirs.reports / "phase_8_preprocessing_flagged.csv"
    with open(flagged_csv, "w", newline="", encoding="utf-8") as ff:
        if flagged_rows:
            w = csv.DictWriter(ff, fieldnames=list(flagged_rows[0].keys()))
            w.writeheader()
            for row in flagged_rows:
                w.writerow(row)
        else:
            ff.write("source_relative_path,status,flag_reason\n")

    final_eligible_records = [r for r in candidate_records if r.relative_path in processed_by_source]
    final_class_counts_num: Dict[int, int] = {g: 0 for g in DR_CANDIDATE_SCHEME}
    for r in final_eligible_records:
        if r.standardized_grade_numeric is not None:
            final_class_counts_num[r.standardized_grade_numeric] += 1

    split_summary = plan_stratified_group_train_val_split(
        eligible_records=final_eligible_records,
        dataset_name="aptos",
        reports_dir=dirs.reports,
        processed_rel_by_source=processed_by_source,
        shared_test_shas=shared_shas,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        seed=seed,
    )

    # Compute empirical normalization stats strictly on TRAIN split
    split_df = pd.read_csv(split_summary["split_manifest_csv"])
    train_proc_rels = split_df[split_df["split"] == "train"]["processed_relative_path"].astype(str).tolist()
    train_channel_stats = _compute_train_channel_stats(processed_aptos, train_proc_rels)

    # Also compute train-only imbalance weights without leaking val counts
    train_class_num = {
        g: int((split_df[split_df["split"] == "train"]["standardized_grade_numeric"] == g).sum())
        for g in DR_CANDIDATE_SCHEME
    }
    train_imbalance = _compute_class_imbalance_strategies(train_class_num)

    # Enrich phase_8_split_summary.json with preprocessing config, normalization stats & imbalance weights
    split_summary["preprocessing_config"] = asdict(config)
    split_summary["preprocessing_log_jsonl"] = str(prep_log_path)
    split_summary["processed_count"] = len(processed_by_source)
    split_summary["flagged_preprocessing_count"] = len(flagged_rows)
    split_summary["flagged_preprocessing_csv"] = str(flagged_csv)
    split_summary["train_split_channel_stats_0_1"] = train_channel_stats
    split_summary["train_split_imbalance_strategies"] = train_imbalance
    split_summary["final_eligible_class_counts"] = {
        DR_CANDIDATE_SCHEME[g]: c for g, c in final_class_counts_num.items()
    }
    with open(split_summary["split_summary_json"], "w", encoding="utf-8") as sjf:
        json.dump(split_summary, sjf, indent=2)

    raw_checksum_audit = verify_raw_checksums_unchanged(raw_aptos, manifest_jsonl)

    exclusion_counts = {
        "Final Eligible Processed (Train+Val)": len(final_eligible_records),
        "Consistent Duplicates Excluded": clean_res["consistent_duplicates_excluded"],
        "Conflict Groups Quarantined": clean_res["conflicting_images_quarantined"],
        "Preprocessing Flagged/Rejected": len(flagged_rows),
        "Official Test Images Excluded": clean_res["raw_test_total"],
    }
    charts = generate_phase8_cleaning_charts(
        raw_class_counts=clean_res["raw_class_counts"],
        eligible_class_counts=split_summary["final_eligible_class_counts"],
        split_counts_by_class=split_summary["class_distribution_by_split"],
        original_dims=original_dims,
        processed_dims=list(set(processed_dims)) if processed_dims else [],
        exclusion_counts=exclusion_counts,
        reports_dir=dirs.reports,
    )

    return {
        "cleaning_summary": {
            k: v
            for k, v in clean_res.items()
            if k not in ("eligible_records", "shared_test_shas", "conflict_shas")
        },
        "split_summary": split_summary,
        "raw_checksum_audit": raw_checksum_audit,
        "charts": charts,
    }
