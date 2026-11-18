import csv
import json
import random
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from data_pipeline.manifest import ManifestRecord


@dataclass(frozen=True)
class SplitAssignment:
    dataset_name: str
    relative_path: str
    sha256_checksum: str
    patient_identifier: Optional[str]
    standardized_label: Optional[str]
    split: str  # 'train', 'val', 'test', 'external_test'
    split_basis: str  # 'external_evaluation_isolated', 'patient_grouped', 'image_level_no_patient_id'


@dataclass(frozen=True)
class SplitPlanResult:
    dataset_name: str
    seed: int
    total_eligible_images: int
    patient_level_split_verified: bool
    limitation_note: str
    counts_by_split: Dict[str, int]
    split_csv_path: str
    split_meta_json_path: str
    assignments: List[SplitAssignment]


def plan_leakage_safe_splits(
    records: List[ManifestRecord],
    dataset_name: str,
    manifests_dir: Path,
    dataset_role: str = "development",  # 'development' or 'external_evaluation'
    train_ratio: float = 0.70,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42,
) -> SplitPlanResult:
    """
    Create reproducible, leakage-aware dataset split assignments from accepted manifest entries.
    - External evaluation datasets (e.g. Messidor-2) are strictly isolated to 'external_test'.
    - When reliable patient identifiers exist on all eligible records, enforces strict
      patient-level grouping so no patient spans train/val/test boundaries.
    - When patient identifiers are absent, explicitly flags patient_level_split_verified=False.
    """
    eligible = [
        r
        for r in sorted(records, key=lambda x: (x.relative_path, x.sha256_checksum or ""))
        if r.validation_status == "accepted"
    ]

    if dataset_role == "external_evaluation":
        assignments = [
            SplitAssignment(
                dataset_name=dataset_name,
                relative_path=r.relative_path,
                sha256_checksum=r.sha256_checksum or "",
                patient_identifier=r.patient_identifier,
                standardized_label=r.standardized_label,
                split="external_test",
                split_basis="external_evaluation_isolated",
            )
            for r in eligible
        ]
        patient_verified = bool(eligible) and all(bool(r.patient_identifier and r.patient_identifier.strip()) for r in eligible)
        limitation = (
            "Dataset designated strictly for external held-out evaluation; never mixed into model training."
        )
        counts = {"train": 0, "val": 0, "test": 0, "external_test": len(assignments)}
    else:
        ratio_sum = train_ratio + val_ratio + test_ratio
        if abs(ratio_sum - 1.0) > 1e-6:
            raise ValueError(f"Split ratios must sum to 1.0 (got {ratio_sum}).")

        rng = random.Random(seed)
        has_all_patient_ids = bool(eligible) and all(
            bool(r.patient_identifier and r.patient_identifier.strip()) for r in eligible
        )

        assignments = []
        counts = {"train": 0, "val": 0, "test": 0, "external_test": 0}

        if has_all_patient_ids:
            # Group strictly by patient_identifier
            by_patient: Dict[str, List[ManifestRecord]] = {}
            for r in eligible:
                pid = str(r.patient_identifier).strip()
                by_patient.setdefault(pid, []).append(r)

            patient_ids = sorted(by_patient.keys())
            rng.shuffle(patient_ids)

            n_patients = len(patient_ids)
            n_train = int(round(n_patients * train_ratio))
            n_val = int(round(n_patients * val_ratio))
            # Ensure at least non-empty splits when enough groups exist
            if n_patients >= 3:
                n_train = max(1, min(n_train, n_patients - 2))
                n_val = max(1, min(n_val, n_patients - n_train - 1))

            train_pids = set(patient_ids[:n_train])
            val_pids = set(patient_ids[n_train : n_train + n_val])

            for pid in sorted(by_patient.keys()):
                if pid in train_pids:
                    split_name = "train"
                elif pid in val_pids:
                    split_name = "val"
                else:
                    split_name = "test"

                for r in by_patient[pid]:
                    assignments.append(
                        SplitAssignment(
                            dataset_name=dataset_name,
                            relative_path=r.relative_path,
                            sha256_checksum=r.sha256_checksum or "",
                            patient_identifier=pid,
                            standardized_label=r.standardized_label,
                            split=split_name,
                            split_basis="patient_grouped",
                        )
                    )
                    counts[split_name] += 1

            patient_verified = True
            limitation = "All records contain patient identifiers; strict patient-level grouping applied."
        else:
            # Explicitly refuse to fabricate patient separation when IDs are absent
            shuffled = list(eligible)
            rng.shuffle(shuffled)
            n_total = len(shuffled)
            n_train = int(round(n_total * train_ratio))
            n_val = int(round(n_total * val_ratio))
            if n_total >= 3:
                n_train = max(1, min(n_train, n_total - 2))
                n_val = max(1, min(n_val, n_total - n_train - 1))

            for idx, r in enumerate(shuffled):
                if idx < n_train:
                    split_name = "train"
                elif idx < n_train + n_val:
                    split_name = "val"
                else:
                    split_name = "test"

                assignments.append(
                    SplitAssignment(
                        dataset_name=dataset_name,
                        relative_path=r.relative_path,
                        sha256_checksum=r.sha256_checksum or "",
                        patient_identifier=r.patient_identifier,
                        standardized_label=r.standardized_label,
                        split=split_name,
                        split_basis="image_level_no_patient_id",
                    )
                )
                counts[split_name] += 1

            patient_verified = False
            limitation = (
                "Patient identifiers are unavailable on all or some records; "
                "seeded image-level split does NOT guarantee patient-level leakage prevention."
            )

    assignments_sorted = sorted(assignments, key=lambda a: (a.split, a.relative_path))
    manifests_dir.mkdir(parents=True, exist_ok=True)
    split_csv_path = manifests_dir / f"{dataset_name}_splits.csv"
    split_meta_json_path = manifests_dir / f"{dataset_name}_splits_meta.json"

    fieldnames = list(SplitAssignment.__dataclass_fields__.keys())
    with open(split_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for a in assignments_sorted:
            writer.writerow(asdict(a))

    meta_payload = {
        "dataset_name": dataset_name,
        "dataset_role": dataset_role,
        "seed": seed,
        "total_eligible_images": len(assignments_sorted),
        "patient_level_split_verified": patient_verified,
        "limitation_note": limitation,
        "counts_by_split": counts,
    }
    with open(split_meta_json_path, "w", encoding="utf-8") as f:
        json.dump(meta_payload, f, indent=2)

    return SplitPlanResult(
        dataset_name=dataset_name,
        seed=seed,
        total_eligible_images=len(assignments_sorted),
        patient_level_split_verified=patient_verified,
        limitation_note=limitation,
        counts_by_split=counts,
        split_csv_path=str(split_csv_path),
        split_meta_json_path=str(split_meta_json_path),
        assignments=assignments_sorted,
    )


def plan_stratified_group_train_val_split(
    eligible_records: List[ManifestRecord],
    dataset_name: str,
    reports_dir: Path,
    processed_rel_by_source: Optional[Dict[str, str]] = None,
    shared_test_shas: Optional[set] = None,
    train_ratio: float = 0.80,
    val_ratio: float = 0.20,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Create a deterministic, SHA-256-group-preserving, class-stratified Train/Val split
    exclusively from verified, conflict-free labeled training records.
    - Explicitly refuses any unlabeled official test records.
    - Guarantees zero SHA-256 duplicate hashes cross the train/val boundary.
    - Explicitly sets patient_level_split_verified=False when patient IDs are unavailable.
    """
    if abs((train_ratio + val_ratio) - 1.0) > 1e-6:
        raise ValueError("train_ratio and val_ratio must sum to 1.0.")

    for r in eligible_records:
        rel_norm = r.relative_path.replace("\\", "/")
        if rel_norm.startswith("test_images/"):
            raise ValueError(f"Official test image '{rel_norm}' cannot enter train/val split.")
        if r.standardized_grade_numeric is None or r.standardized_label is None:
            raise ValueError(f"Record '{rel_norm}' lacks verified numeric DR grade.")
        if not r.sha256_checksum:
            raise ValueError(f"Record '{rel_norm}' missing SHA-256 checksum for group isolation.")

    reports_dir.mkdir(parents=True, exist_ok=True)
    proc_map = processed_rel_by_source or {}
    overlap_shas = shared_test_shas or set()

    # Group eligible records by SHA-256 checksum (each group stays strictly atomic)
    groups_by_sha: Dict[str, List[ManifestRecord]] = {}
    for r in sorted(eligible_records, key=lambda x: x.relative_path):
        groups_by_sha.setdefault(r.sha256_checksum or "", []).append(r)

    # Verify label agreement inside every group before splitting
    shas_by_grade: Dict[int, List[str]] = {}
    for sha, grp in sorted(groups_by_sha.items()):
        grades = {g.standardized_grade_numeric for g in grp}
        if len(grades) != 1:
            raise ValueError(f"Unquarantined conflicting labels in SHA group '{sha}'.")
        grade = int(next(iter(grades)))  # type: ignore[arg-type]
        shas_by_grade.setdefault(grade, []).append(sha)

    rng = random.Random(seed)
    sha_to_split: Dict[str, str] = {}

    for grade in sorted(shas_by_grade.keys()):
        grade_shas = sorted(shas_by_grade[grade])
        rng.shuffle(grade_shas)
        n_grp = len(grade_shas)
        if n_grp >= 2:
            n_val = max(1, min(n_grp - 1, int(round(n_grp * val_ratio))))
        else:
            n_val = 0
        val_set = set(grade_shas[:n_val])
        for sha in grade_shas:
            sha_to_split[sha] = "val" if sha in val_set else "train"

    manifest_rows: List[Dict[str, Any]] = []
    train_shas: set = set()
    val_shas: set = set()
    class_counts_by_split: Dict[str, Dict[str, int]] = {"train": {}, "val": {}}

    for sha, grp in sorted(groups_by_sha.items()):
        split_name = sha_to_split[sha]
        if split_name == "train":
            train_shas.add(sha)
        else:
            val_shas.add(sha)

        for r in grp:
            lbl = str(r.standardized_label)
            class_counts_by_split[split_name][lbl] = class_counts_by_split[split_name].get(lbl, 0) + 1
            manifest_rows.append(
                {
                    "dataset_name": dataset_name,
                    "relative_path": r.relative_path,
                    "processed_relative_path": proc_map.get(r.relative_path, ""),
                    "sha256_checksum": sha,
                    "raw_label": r.raw_label,
                    "standardized_label": lbl,
                    "standardized_grade_numeric": r.standardized_grade_numeric,
                    "overlaps_official_test_sha256": sha in overlap_shas,
                    "split": split_name,
                    "split_basis": "stratified_sha256_grouped_no_patient_id",
                    "seed": seed,
                }
            )

    if train_shas & val_shas:
        raise RuntimeError("Invariant violated: exact SHA-256 overlap detected between train and val splits!")

    manifest_rows.sort(key=lambda row: (row["split"], row["relative_path"]))

    split_csv = reports_dir / "phase_8_split_manifest.csv"
    fieldnames = [
        "dataset_name",
        "relative_path",
        "processed_relative_path",
        "sha256_checksum",
        "raw_label",
        "standardized_label",
        "standardized_grade_numeric",
        "overlaps_official_test_sha256",
        "split",
        "split_basis",
        "seed",
    ]
    with open(split_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for row in manifest_rows:
            w.writerow(row)

    train_total = sum(class_counts_by_split["train"].values())
    val_total = sum(class_counts_by_split["val"].values())
    patient_verified = bool(eligible_records) and all(
        bool(r.patient_identifier and str(r.patient_identifier).strip()) for r in eligible_records
    )

    limitation_note = (
        "Patient identifiers are unavailable on APTOS 2019; stratified exact-SHA256-grouped split "
        "prevents exact-image leakage across train/val, but patient-level separation and clinical independence CANNOT be guaranteed. "
        "Official unlabeled test_images are excluded from train and val."
    )

    split_summary = {
        "dataset_name": dataset_name,
        "seed": seed,
        "train_ratio_target": train_ratio,
        "val_ratio_target": val_ratio,
        "total_eligible_images": len(manifest_rows),
        "train_count": train_total,
        "val_count": val_total,
        "train_pct": round((train_total / len(manifest_rows)) * 100.0, 2) if manifest_rows else 0.0,
        "val_pct": round((val_total / len(manifest_rows)) * 100.0, 2) if manifest_rows else 0.0,
        "class_distribution_by_split": class_counts_by_split,
        "class_percentages_by_split": {
            sp: {
                lbl: round((cnt / (train_total if sp == "train" else val_total)) * 100.0, 2)
                for lbl, cnt in sorted(dist.items())
            }
            for sp, dist in class_counts_by_split.items()
            if (train_total if sp == "train" else val_total) > 0
        },
        "exact_sha256_overlap_between_train_and_val": len(train_shas & val_shas),
        "official_test_images_included": 0,
        "patient_identifiers_available": patient_verified,
        "patient_level_split_verified": patient_verified,
        "clinically_independent_split_guaranteed": False,
        "limitation_note": limitation_note,
        "split_manifest_csv": str(split_csv),
    }

    summary_json = reports_dir / "phase_8_split_summary.json"
    with open(summary_json, "w", encoding="utf-8") as jf:
        json.dump(split_summary, jf, indent=2)
    split_summary["split_summary_json"] = str(summary_json)

    return split_summary
