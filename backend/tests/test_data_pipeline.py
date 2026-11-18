import csv
import hashlib
import io
import json
import os
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from data_pipeline.audit_reporter import generate_dataset_audit_report
from data_pipeline.directory_manager import (
    DatasetDirectoryError,
    DatasetDirectoryManager,
)
from data_pipeline.importers import load_aptos_items, load_drive_items, load_messidor2_items
from data_pipeline.inspector import DatasetInputItem, DatasetInspector
from data_pipeline.label_mapping import map_dr_label
from data_pipeline.manifest import read_manifest_jsonl
from data_pipeline.preprocessor import DatasetPreprocessor, PreprocessingConfig
from data_pipeline.registry import export_dataset_inventory_csv, export_dataset_summary_json
from data_pipeline.split_planner import plan_leakage_safe_splits


def _write_synthetic_image(
    path: Path,
    fmt: str = "PNG",
    size=(160, 120),
    color=(120, 60, 40),
    noise_seed: int | None = None,
    exif_orientation: int | None = None,
) -> bytes:
    path.parent.mkdir(parents=True, exist_ok=True)
    if noise_seed is not None:
        rng = np.random.default_rng(noise_seed)
        arr = rng.integers(0, 255, size=(size[1], size[0], 3), dtype=np.uint8)
        img = Image.fromarray(arr, mode="RGB")
    else:
        img = Image.new("RGB", size, color=color)

    buf = io.BytesIO()
    if exif_orientation is not None and fmt.upper() == "JPEG":
        exif = img.getexif()
        exif[274] = exif_orientation
        img.save(buf, format="JPEG", exif=exif, quality=92)
    else:
        img.save(buf, format=fmt)
    raw = buf.getvalue()
    path.write_bytes(raw)
    return raw


def test_dataset_directory_configuration_and_security_boundaries(tmp_path: Path):
    """Verify configurable directory tree provisioning and safety rejections against public/clinical paths."""
    ds_root = tmp_path / "isolated_datasets"
    mgr = DatasetDirectoryManager(str(ds_root))
    dirs = mgr.ensure_structure()

    assert dirs.root == ds_root.resolve()
    assert dirs.raw.is_dir()
    for ds_key in ("aptos", "idrid", "messidor2", "drive"):
        assert dirs.raw_by_dataset[ds_key].is_dir()
    for sub in (dirs.manifests, dirs.processed, dirs.rejected, dirs.reports, dirs.temporary):
        assert sub.is_dir()

    # Must reject overlapping Next.js public static directory
    repo_root = Path(__file__).resolve().parent.parent.parent
    public_dir = repo_root / "public"
    with pytest.raises(DatasetDirectoryError):
        DatasetDirectoryManager(str(public_dir / "datasets"))

    # Empty root string rejected
    with pytest.raises(DatasetDirectoryError):
        DatasetDirectoryManager("   ")


def test_permission_and_filesystem_errors(tmp_path: Path):
    """Verify filesystem/permission errors fail cleanly with descriptive exceptions."""
    ds_root = tmp_path / "perm_datasets"
    with patch("os.access", return_value=False):
        mgr = DatasetDirectoryManager(str(ds_root))
        with pytest.raises(DatasetDirectoryError):
            mgr.ensure_structure()

    # Unreadable image file logged as rejected cleanly
    raw_dir = tmp_path / "raw_perm"
    img_path = raw_dir / "unreadable.png"
    _write_synthetic_image(img_path, fmt="PNG")
    inspector = DatasetInspector()

    with patch("os.access", return_value=False):
        records, summary = inspector.inspect_dataset(
            dataset_name="synthetic_test",
            raw_dataset_dir=raw_dir,
            items=[DatasetInputItem(relative_path="unreadable.png", raw_label="0")],
            manifests_dir=tmp_path / "manifests",
            rejected_dir=tmp_path / "rejected",
            fixed_timestamp="2026-11-11T00:00:00+00:00",
        )
    assert summary.rejected_count == 1
    assert "permissions" in (records[0].rejection_reason or "").lower()


def test_manifest_validation_corrupt_duplicates_missing_and_labels(tmp_path: Path):
    """
    Verify genuine inspection of valid, empty, corrupt, tiny, duplicate SHA-256,
    near-duplicate dHash, missing image, missing label, invalid label, and duplicate collision entries.
    """
    dirs = DatasetDirectoryManager(str(tmp_path / "ds")).ensure_structure()
    raw_dir = dirs.raw / "aptos"

    # 1. Valid unique images (distinct procedural noise patterns so dHash doesn't match)
    valid_bytes_0 = _write_synthetic_image(raw_dir / "train_images" / "img_000.png", fmt="PNG", noise_seed=101)
    _write_synthetic_image(raw_dir / "train_images" / "img_002.png", fmt="PNG", noise_seed=202)

    # 2. Exact byte-for-byte duplicate of img_000.png
    (raw_dir / "train_images" / "img_000_dup.png").write_bytes(valid_bytes_0)

    # 3. Near-duplicate (solid identical pattern, different encoding format)
    _write_synthetic_image(raw_dir / "train_images" / "img_near_a.png", fmt="PNG", color=(100, 100, 100))
    _write_synthetic_image(raw_dir / "train_images" / "img_near_b.jpg", fmt="JPEG", color=(102, 100, 100))

    # 4. Corrupt truncated JPEG
    jpeg_bytes = _write_synthetic_image(raw_dir / "train_images" / "temp_ok.jpg", fmt="JPEG", noise_seed=303)
    (raw_dir / "train_images" / "corrupt.jpg").write_bytes(jpeg_bytes[: len(jpeg_bytes) // 3])
    (raw_dir / "train_images" / "temp_ok.jpg").unlink()

    # 5. Empty 0-byte file
    (raw_dir / "train_images" / "empty.png").write_bytes(b"")

    # 6. Unsupported dimensions (< min_dimension)
    _write_synthetic_image(raw_dir / "train_images" / "tiny.png", fmt="PNG", size=(10, 10))

    items = [
        DatasetInputItem(relative_path="train_images/img_000.png", raw_label="0"),
        DatasetInputItem(relative_path="train_images/img_002.png", raw_label="2"),
        DatasetInputItem(relative_path="train_images/img_000_dup.png", raw_label="0"),
        # Collision duplicate path entry
        DatasetInputItem(relative_path="train_images/img_000.png", raw_label="0"),
        DatasetInputItem(relative_path="train_images/img_near_a.png", raw_label="1"),
        DatasetInputItem(relative_path="train_images/img_near_b.jpg", raw_label="1"),
        DatasetInputItem(relative_path="train_images/corrupt.jpg", raw_label="3"),
        DatasetInputItem(relative_path="train_images/empty.png", raw_label="0"),
        DatasetInputItem(relative_path="train_images/tiny.png", raw_label="0"),
        DatasetInputItem(relative_path="train_images/does_not_exist.png", raw_label="4"),
        DatasetInputItem(relative_path="train_images/img_missing_lbl.png", raw_label=""),
        DatasetInputItem(relative_path="train_images/img_bad_lbl.png", raw_label="99"),
    ]
    _write_synthetic_image(raw_dir / "train_images" / "img_missing_lbl.png", fmt="PNG", noise_seed=404)
    _write_synthetic_image(raw_dir / "train_images" / "img_bad_lbl.png", fmt="PNG", noise_seed=505)

    inspector = DatasetInspector(min_dimension=32)
    records, summary = inspector.inspect_dataset(
        dataset_name="aptos",
        raw_dataset_dir=raw_dir,
        items=items,
        manifests_dir=dirs.manifests,
        rejected_dir=dirs.rejected,
        require_valid_label=True,
        fixed_timestamp="2026-11-11T00:00:00+00:00",
    )

    assert summary.total_entries_inspected == 12
    assert summary.accepted_count == 4  # img_000, img_002, img_near_a, img_near_b
    assert summary.duplicate_exact_count == 1  # img_000_dup.png
    assert summary.missing_image_count == 1  # does_not_exist.png
    assert summary.missing_label_count == 1  # img_missing_lbl.png
    assert summary.invalid_label_count == 1  # img_bad_lbl.png
    assert summary.rejected_count == 6  # collision + corrupt + empty + tiny + missing_lbl + bad_lbl
    assert summary.near_duplicate_candidate_count >= 1  # img_near_b flagged without auto-removal

    # Verify manifest files written reproducibly
    csv_path = Path(summary.manifest_csv_path)
    jsonl_path = Path(summary.manifest_jsonl_path)
    rej_path = Path(summary.rejected_csv_path)
    assert csv_path.is_file() and jsonl_path.is_file() and rej_path.is_file()

    # Re-run inspection to verify 100% deterministic reproducible output
    csv_first = csv_path.read_text(encoding="utf-8")
    inspector.inspect_dataset(
        dataset_name="aptos",
        raw_dataset_dir=raw_dir,
        items=list(reversed(items)),  # Shuffled input order must still produce identical CSV!
        manifests_dir=dirs.manifests,
        rejected_dir=dirs.rejected,
        require_valid_label=True,
        fixed_timestamp="2026-11-11T00:00:00+00:00",
    )
    csv_second = csv_path.read_text(encoding="utf-8")
    assert csv_first == csv_second

    # Audit report & actual Matplotlib charts generated cleanly
    audit = generate_dataset_audit_report("aptos", records, dirs.reports, generate_charts=True)
    assert audit["valid_images"] == 4
    assert len(audit["charts_generated"]) == 3
    for chart in audit["charts_generated"]:
        assert Path(chart).is_file()


def test_label_mapping_rules_and_task_separation():
    """Verify strict DR 0..4 mapping, unresolved Messidor ungradable handling, and non-DR mask isolation."""
    # APTOS valid 0..4
    assert map_dr_label("aptos", "0").standardized_label == "NO_DR"
    assert map_dr_label("aptos", "4").standardized_label == "PDR"
    assert map_dr_label("aptos", "5").mapping_status == "unresolved"
    assert map_dr_label("aptos", "-1").mapping_status == "unresolved"
    assert map_dr_label("aptos", "").mapping_status == "missing"

    # Messidor-2 ungradable never forced to NO_DR
    m_ungrad = map_dr_label("messidor2", "0", gradable_flag="0")
    assert m_ungrad.mapping_status == "unresolved"
    assert m_ungrad.standardized_label is None

    m_grad = map_dr_label("messidor2", "2", gradable_flag="1")
    assert m_grad.mapping_status == "mapped"
    assert m_grad.standardized_label == "MODERATE_NPDR"

    # IDRiD lesion segmentation and DRIVE vessel segmentation strictly kept distinct
    idrid_seg = map_dr_label("idrid", "2", task_type="lesion_segmentation")
    assert idrid_seg.mapping_status == "non_dr_task"
    assert idrid_seg.standardized_label is None

    drive_res = map_dr_label("drive", "1")
    assert drive_res.mapping_status == "non_dr_task"
    assert drive_res.standardized_label is None


def test_raw_image_preservation_and_reversible_preprocessing(tmp_path: Path):
    """
    Verify preprocessing never alters raw files, handles EXIF orientation cleanly,
    converts color mode cleanly, preserves aspect ratio via letterbox padding, and logs transforms.
    """
    dirs = DatasetDirectoryManager(str(tmp_path / "ds_prep")).ensure_structure()
    raw_dir = dirs.raw / "aptos"
    img_path = raw_dir / "train_images" / "exif_sample.jpg"
    # Wide rectangular image (200x100) with EXIF orientation=6 (90 deg rotation -> becomes 100x200)
    raw_bytes_before = _write_synthetic_image(
        img_path, fmt="JPEG", size=(200, 100), color=(90, 140, 80), exif_orientation=6
    )
    sha_before = hashlib.sha256(raw_bytes_before).hexdigest()

    inspector = DatasetInspector(min_dimension=32)
    records, _ = inspector.inspect_dataset(
        dataset_name="aptos",
        raw_dataset_dir=raw_dir,
        items=[DatasetInputItem(relative_path="train_images/exif_sample.jpg", raw_label="1")],
        manifests_dir=dirs.manifests,
        rejected_dir=dirs.rejected,
        fixed_timestamp="2026-11-11T00:00:00+00:00",
    )

    prep = DatasetPreprocessor(PreprocessingConfig(target_size=(256, 256), output_format="PNG"))
    prep_records, log_path = prep.run(
        dataset_name="aptos",
        records=records,
        raw_dataset_dir=raw_dir,
        processed_dataset_dir=dirs.processed / "aptos",
        manifests_dir=dirs.manifests,
    )

    # 1. Raw image must be 100% untouched byte-for-byte
    assert img_path.read_bytes() == raw_bytes_before
    assert hashlib.sha256(img_path.read_bytes()).hexdigest() == sha_before

    # 2. Processed copy resides separately in processed/ with target dimensions and aspect preservation
    assert len(prep_records) == 1
    pr = prep_records[0]
    assert pr.exif_orientation_transposed is True
    assert pr.aspect_ratio_preserved is True
    assert (pr.processed_width, pr.processed_height) == (256, 256)
    assert pr.processed_mode == "RGB"
    out_file = dirs.processed / "aptos" / pr.processed_relative_path
    assert out_file.is_file()
    assert log_path.is_file()
    log_lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(log_lines) == 2
    cfg_entry = json.loads(log_lines[0])["_preprocessing_config"]
    assert cfg_entry["clahe_applied"] is False
    assert cfg_entry["model_normalization_applied"] is False


def test_patient_level_split_safeguards_and_external_isolation(tmp_path: Path):
    """
    Verify:
    1) Patient-grouped datasets keep all images of each patient together across splits (zero leakage).
    2) Datasets lacking patient IDs explicitly record patient_level_split_verified=False.
    3) External evaluation datasets isolate 100% of records into 'external_test'.
    """
    dirs = DatasetDirectoryManager(str(tmp_path / "ds_split")).ensure_structure()

    def _rec(path: str, pid: str | None, lbl: str = "0"):
        from data_pipeline.manifest import ManifestRecord
        return ManifestRecord(
            dataset_name="testds",
            original_filename=Path(path).name,
            relative_path=path,
            file_extension=".png",
            detected_media_type="image/png",
            file_size_bytes=1000,
            width=256,
            height=256,
            channels=3,
            sha256_checksum=hashlib.sha256(path.encode()).hexdigest(),
            perceptual_hash="0" * 16,
            raw_label=lbl,
            standardized_label="NO_DR",
            standardized_grade_numeric=0,
            label_mapping_status="mapped",
            label_mapping_rationale="ok",
            annotation_availability="test",
            patient_identifier=pid,
            patient_id_limitation_note="ok" if pid else "missing",
            import_timestamp="2026-11-11T00:00:00+00:00",
            validation_status="accepted",
            rejection_reason=None,
        )

    # Case A: 6 distinct patients x 2 eyes each = 12 images -> zero patient overlap allowed across splits!
    patient_records = []
    for p_idx in range(6):
        pid = f"PAT_{p_idx:03d}"
        patient_records.append(_rec(f"p{p_idx}_od.png", pid))
        patient_records.append(_rec(f"p{p_idx}_os.png", pid))

    plan_grouped = plan_leakage_safe_splits(
        records=patient_records,
        dataset_name="grouped_cohort",
        manifests_dir=dirs.manifests,
        dataset_role="development",
        seed=42,
    )
    assert plan_grouped.patient_level_split_verified is True
    splits_by_pid = {}
    for a in plan_grouped.assignments:
        splits_by_pid.setdefault(a.patient_identifier, set()).add(a.split)
    assert all(len(s) == 1 for s in splits_by_pid.values()), "Patient leaked across multiple splits!"

    # Case B: Missing patient IDs -> explicitly sets patient_level_split_verified=False
    no_pid_records = [_rec(f"img_{i}.png", None) for i in range(6)]
    plan_no_pid = plan_leakage_safe_splits(
        records=no_pid_records,
        dataset_name="aptos_like",
        manifests_dir=dirs.manifests,
        dataset_role="development",
        seed=42,
    )
    assert plan_no_pid.patient_level_split_verified is False
    assert "does not guarantee" in plan_no_pid.limitation_note.lower()

    # Case C: External evaluation (Messidor-2) -> strictly 100% external_test
    plan_ext = plan_leakage_safe_splits(
        records=patient_records,
        dataset_name="messidor2",
        manifests_dir=dirs.manifests,
        dataset_role="external_evaluation",
        seed=42,
    )
    assert plan_ext.counts_by_split["train"] == 0
    assert plan_ext.counts_by_split["val"] == 0
    assert plan_ext.counts_by_split["external_test"] == 12


def test_empty_dataset_and_importer_layouts(tmp_path: Path):
    """Verify empty directory graceful handling and synthetic APTOS/DRIVE layout importers + registry export."""
    dirs = DatasetDirectoryManager(str(tmp_path / "ds_empty")).ensure_structure()
    inspector = DatasetInspector()
    empty_recs, empty_sum = inspector.inspect_dataset(
        dataset_name="aptos",
        raw_dataset_dir=dirs.raw / "aptos",
        items=load_aptos_items(dirs.raw / "aptos"),
        manifests_dir=dirs.manifests,
        rejected_dir=dirs.rejected,
    )
    assert empty_sum.total_entries_inspected == 0
    assert empty_sum.accepted_count == 0
    empty_audit = generate_dataset_audit_report("aptos", empty_recs, dirs.reports)
    assert empty_audit["valid_images"] == 0
    assert empty_audit["charts_generated"] == []

    # Synthetic DRIVE vessel mask dimension mismatch & match check
    drive_raw = dirs.raw / "drive"
    _write_synthetic_image(drive_raw / "training" / "images" / "21_training.tif", fmt="TIFF", size=(160, 160))
    _write_synthetic_image(drive_raw / "training" / "1st_manual" / "21_manual1.gif", fmt="GIF", size=(160, 160))
    drive_items = load_drive_items(drive_raw)
    assert len(drive_items) == 1
    d_recs, d_sum = inspector.inspect_dataset(
        dataset_name="drive",
        raw_dataset_dir=drive_raw,
        items=drive_items,
        manifests_dir=dirs.manifests,
        rejected_dir=dirs.rejected,
    )
    assert d_sum.accepted_count == 1
    assert d_recs[0].label_mapping_status == "non_dr_task"

    # Verify inventory export
    inv_csv = export_dataset_inventory_csv(dirs.reports / "phase_5_dataset_inventory.csv")
    sum_json = export_dataset_summary_json(dirs.reports / "phase_5_dataset_summary.json", str(dirs.root))
    assert inv_csv.is_file() and sum_json.is_file()
    parsed_summary = json.loads(sum_json.read_text(encoding="utf-8"))
    assert parsed_summary["datasets_actually_downloaded"] == []
    assert set(parsed_summary["datasets_only_investigated"]) == {"aptos", "idrid", "messidor2", "drive"}
