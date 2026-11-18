import argparse
import json
from pathlib import Path
from typing import Optional

from dataclasses import asdict
from data_pipeline.archive_importer import (
    check_dataset_acquisition_readiness,
    import_dataset_archive,
    verify_raw_checksums_unchanged,
)
from data_pipeline.cleaning import run_phase8_aptos_pipeline
from data_pipeline.audit_reporter import generate_dataset_audit_report
from data_pipeline.directory_manager import DatasetDirectoryManager
from data_pipeline.importers import (
    load_aptos_items,
    load_drive_items,
    load_generic_items,
    load_idrid_items,
    load_messidor2_items,
)
from data_pipeline.inspector import DatasetInspector
from data_pipeline.manifest import read_manifest_jsonl
from data_pipeline.preprocessor import DatasetPreprocessor, PreprocessingConfig
from data_pipeline.quality_audit import inspect_cross_dataset_quality
from data_pipeline.registry import (
    export_dataset_inventory_csv,
    export_dataset_summary_json,
    export_phase6_reports,
)
from data_pipeline.split_planner import plan_leakage_safe_splits


def _load_items_for_dataset(dataset: str, raw_dir: Path, labels_csv: Optional[Path] = None):
    ds = dataset.lower()
    if ds == "aptos":
        return load_aptos_items(raw_dir)
    if ds == "idrid":
        return load_idrid_items(raw_dir)
    if ds == "messidor2":
        return load_messidor2_items(raw_dir)
    if ds == "drive":
        return load_drive_items(raw_dir)
    return load_generic_items(raw_dir, labels_csv=labels_csv)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="RETIVUE Phase 5 Dataset Engineering Pipeline CLI")
    parser.add_argument("--dataset-root", default=None, help="Override DATASET_ROOT directory")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Provision configurable dataset directory hierarchy outside Git")
    sub.add_parser("inventory", help="Export verified dataset research inventory CSV & summary JSON")

    p_inspect = sub.add_parser("inspect", help="Inspect raw dataset files, validate, deduplicate & emit reports")
    p_inspect.add_argument("--dataset", required=True, help="Dataset key (aptos, idrid, messidor2, drive, or custom)")
    p_inspect.add_argument("--labels-csv", default=None, help="Optional labels CSV for generic datasets")
    p_inspect.add_argument("--allow-missing-labels", action="store_true", help="Do not reject images missing labels")

    p_prep = sub.add_parser("preprocess", help="Run reversible aspect-preserving preprocessing into processed/")
    p_prep.add_argument("--dataset", required=True)
    p_prep.add_argument("--width", type=int, default=None, help="Optional letterbox target width")
    p_prep.add_argument("--height", type=int, default=None, help="Optional letterbox target height")

    p_split = sub.add_parser("plan-splits", help="Generate leakage-aware split manifest CSV & metadata")
    p_split.add_argument("--dataset", required=True)
    p_split.add_argument("--role", choices=["development", "external_evaluation"], default="development")
    p_split.add_argument("--seed", type=int, default=42)

    sub.add_parser("check-readiness", help="Check local credentials, disk headroom & dataset acquisition status")

    p_import = sub.add_parser("import-archive", help="Verify, preserve, and safely extract a local dataset archive")
    p_import.add_argument("--dataset", required=True, help="Dataset key (aptos, idrid, messidor2, drive, or custom)")
    p_import.add_argument("--archive", required=True, help="Path to authorized local .zip/.tar/.tar.gz archive")
    p_import.add_argument("--expected-sha256", default=None, help="Optional expected archive SHA-256 hex digest")
    p_import.add_argument("--overwrite", action="store_true", help="Allow overwriting existing raw files/archive")

    p_vchk = sub.add_parser("verify-checksums", help="Verify raw image SHA-256 checksums match manifest")
    p_vchk.add_argument("--dataset", required=True)

    sub.add_parser("quality-audit", help="Run cross-dataset duplicate/leakage audit & export Phase 6 inventory")

    p_p8 = sub.add_parser("phase8-run", help="Run Phase 8 cleaning, FOV cropping preprocessing & stratified group splits")
    p_p8.add_argument("--target-size", type=int, default=512, help="Square letterbox output size (default 512)")
    p_p8.add_argument("--seed", type=int, default=42, help="Deterministic split random seed")
    p_p8.add_argument("--clahe", action="store_true", help="Enable optional LAB CLAHE enhancement")
    p_p8.add_argument(
        "--exclude-test-overlapping-train",
        action="store_true",
        help="Also drop training images whose SHA-256 matches unlabeled official test_images",
    )

    args = parser.parse_args(argv)
    mgr = DatasetDirectoryManager(root_override=args.dataset_root)
    dirs = mgr.ensure_structure()

    if args.command == "init":
        print(json.dumps({"initialized_dataset_root": str(dirs.root)}, indent=2))
        return 0

    if args.command == "inventory":
        inv_csv = export_dataset_inventory_csv(dirs.reports / "phase_5_dataset_inventory.csv")
        sum_json = export_dataset_summary_json(dirs.reports / "phase_5_dataset_summary.json", str(dirs.root))
        print(json.dumps({"inventory_csv": str(inv_csv), "summary_json": str(sum_json)}, indent=2))
        return 0

    if args.command == "inspect":
        ds_dir = dirs.raw_by_dataset.get(args.dataset.lower(), dirs.raw / args.dataset)
        labels_csv = Path(args.labels_csv) if args.labels_csv else None
        items = _load_items_for_dataset(args.dataset, ds_dir, labels_csv=labels_csv)
        inspector = DatasetInspector()
        records, summary = inspector.inspect_dataset(
            dataset_name=args.dataset,
            raw_dataset_dir=ds_dir,
            items=items,
            manifests_dir=dirs.manifests,
            rejected_dir=dirs.rejected,
            require_valid_label=not args.allow_missing_labels,
        )
        audit = generate_dataset_audit_report(args.dataset, records, dirs.reports)
        print(json.dumps({"inspection_summary": summary.__dict__, "audit_report": audit}, indent=2))
        return 0

    if args.command == "preprocess":
        manifest_path = dirs.manifests / f"{args.dataset}_manifest.jsonl"
        records = read_manifest_jsonl(manifest_path)
        ds_dir = dirs.raw_by_dataset.get(args.dataset.lower(), dirs.raw / args.dataset)
        target_size = (args.width, args.height) if args.width and args.height else None
        prep = DatasetPreprocessor(PreprocessingConfig(target_size=target_size))
        res, log_path = prep.run(
            dataset_name=args.dataset,
            records=records,
            raw_dataset_dir=ds_dir,
            processed_dataset_dir=dirs.processed / args.dataset,
            manifests_dir=dirs.manifests,
        )
        print(json.dumps({"processed_count": len(res), "log_path": str(log_path)}, indent=2))
        return 0

    if args.command == "plan-splits":
        manifest_path = dirs.manifests / f"{args.dataset}_manifest.jsonl"
        records = read_manifest_jsonl(manifest_path)
        plan = plan_leakage_safe_splits(
            records=records,
            dataset_name=args.dataset,
            manifests_dir=dirs.manifests,
            dataset_role=args.role,
            seed=args.seed,
        )
        print(
            json.dumps(
                {
                    "split_csv": plan.split_csv_path,
                    "split_meta": plan.split_meta_json_path,
                    "patient_level_split_verified": plan.patient_level_split_verified,
                    "counts_by_split": plan.counts_by_split,
                    "limitation_note": plan.limitation_note,
                },
                indent=2,
            )
        )
        return 0

    if args.command == "check-readiness":
        readiness = check_dataset_acquisition_readiness(dirs)
        print(json.dumps(readiness, indent=2))
        return 0

    if args.command == "import-archive":
        rec = import_dataset_archive(
            dataset_name=args.dataset,
            archive_source_path=Path(args.archive),
            dirs=dirs,
            expected_sha256=args.expected_sha256,
            allow_overwrite=args.overwrite,
        )
        print(json.dumps(asdict(rec), indent=2))
        return 0 if rec.status == "imported" else 2

    if args.command == "verify-checksums":
        ds_dir = dirs.raw_by_dataset.get(args.dataset.lower(), dirs.raw / args.dataset)
        manifest_path = dirs.manifests / f"{args.dataset}_manifest.jsonl"
        res = verify_raw_checksums_unchanged(ds_dir, manifest_path)
        print(json.dumps(res, indent=2))
        return 0 if res.get("all_unchanged", False) else 2

    if args.command == "quality-audit":
        readiness = check_dataset_acquisition_readiness(dirs)
        quality = inspect_cross_dataset_quality(dirs)
        inv_csv, sum_json = export_phase6_reports(
            dirs.reports / "phase_6_dataset_inventory.csv",
            dirs.reports / "phase_6_dataset_summary.json",
            quality,
            readiness,
        )
        print(json.dumps({"quality_audit": quality, "inventory_csv": str(inv_csv), "summary_json": str(sum_json)}, indent=2))
        return 0

    if args.command == "phase8-run":
        result = run_phase8_aptos_pipeline(
            dirs=dirs,
            target_size=args.target_size,
            clahe_applied=args.clahe,
            seed=args.seed,
            exclude_train_overlapping_test=args.exclude_test_overlapping_train,
        )
        print(json.dumps(result, indent=2))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
