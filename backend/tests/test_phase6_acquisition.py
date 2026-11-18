"""Phase 6 unit and safety tests for archive ingestion, interrupted imports, and cross-dataset auditing."""

import io
import json
import zipfile
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
from PIL import Image

from data_pipeline.archive_importer import (
    check_dataset_acquisition_readiness,
    import_dataset_archive,
    verify_raw_checksums_unchanged,
)
from data_pipeline.directory_manager import DatasetDirectoryManager
from data_pipeline.importers import load_aptos_items, load_drive_items, load_idrid_items, load_messidor2_items
from data_pipeline.inspector import DatasetInspector
from data_pipeline.preprocessor import DatasetPreprocessor, PreprocessingConfig
from data_pipeline.quality_audit import inspect_cross_dataset_quality
from data_pipeline.registry import export_phase6_reports


def _make_png_bytes(size=(128, 96), seed: int = 1) -> bytes:
    rng = np.random.default_rng(seed)
    arr = rng.integers(0, 255, size=(size[1], size[0], 3), dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr, mode="RGB").save(buf, format="PNG")
    return buf.getvalue()


def test_readiness_honestly_reports_missing_credentials_and_archives(tmp_path: Path):
    """When neither Kaggle credentials nor local archives exist, readiness strictly reports awaiting_authorization."""
    mgr = DatasetDirectoryManager(str(tmp_path / "ds"))
    dirs = mgr.ensure_structure()
    assert dirs.archives.is_dir()

    fake_home = tmp_path / "empty_home"
    fake_home.mkdir()
    with patch("pathlib.Path.home", return_value=fake_home), patch.dict(
        "os.environ", {"KAGGLE_USERNAME": "", "KAGGLE_KEY": ""}, clear=False
    ):
        readiness = check_dataset_acquisition_readiness(dirs)

    assert readiness["kaggle_credentials"]["any_kaggle_credentials_present"] is False
    assert len(readiness["datasets"]) == 4
    assert all(d["phase6_status"] == "awaiting_authorization" for d in readiness["datasets"])
    assert all(d["raw_files_on_disk"] == 0 for d in readiness["datasets"])


def test_missing_corrupt_checksum_mismatch_and_zip_slip_archives(tmp_path: Path):
    """Verify missing archive, corrupt archive, checksum mismatch, and Zip Slip path traversal fail cleanly."""
    mgr = DatasetDirectoryManager(str(tmp_path / "ds"))
    dirs = mgr.ensure_structure()

    # 1. Missing archive
    missing_rec = import_dataset_archive("aptos", tmp_path / "does_not_exist.zip", dirs)
    assert missing_rec.status == "missing_archive"
    assert missing_rec.extracted_files_count == 0

    # 2. Checksum mismatch
    valid_zip = tmp_path / "sample.zip"
    with zipfile.ZipFile(valid_zip, "w") as zf:
        zf.writestr("train_images/img1.png", _make_png_bytes(seed=7))
        zf.writestr("train.csv", "id_code,diagnosis\nimg1,0\n")

    mismatch_rec = import_dataset_archive(
        "aptos", valid_zip, dirs, expected_sha256="0" * 64
    )
    assert mismatch_rec.status == "checksum_mismatch"
    assert list(dirs.raw_by_dataset["aptos"].rglob("*")) == []

    # 3. Corrupt / truncated archive
    corrupt_zip = tmp_path / "truncated.zip"
    raw_zip_bytes = valid_zip.read_bytes()
    corrupt_zip.write_bytes(raw_zip_bytes[: max(10, len(raw_zip_bytes) // 2)])

    corrupt_rec = import_dataset_archive("aptos", corrupt_zip, dirs)
    assert corrupt_rec.status == "corrupt_archive"
    assert list(dirs.raw_by_dataset["aptos"].rglob("*")) == []

    # 4. Path traversal (Zip Slip)
    slip_zip = tmp_path / "evil_slip.zip"
    with zipfile.ZipFile(slip_zip, "w") as zf:
        zf.writestr("../../outside_escape.txt", "blocked")

    slip_rec = import_dataset_archive("aptos", slip_zip, dirs)
    assert slip_rec.status == "corrupt_archive"
    assert "traversal" in (slip_rec.error_detail or "").lower()
    assert not (tmp_path / "outside_escape.txt").exists()

    # Verify all failure attempts are recorded in acquisition log
    log_lines = (dirs.manifests / "aptos_acquisition_log.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(log_lines) == 4


def test_interrupted_import_cleanup_and_overwrite_protection(tmp_path: Path):
    """
    Interrupted extraction must leave raw/<dataset>/ empty and clean up temporary staging dirs;
    subsequent imports into populated raw/<dataset>/ must block overwrites cleanly.
    """
    mgr = DatasetDirectoryManager(str(tmp_path / "ds"))
    dirs = mgr.ensure_structure()

    arch_path = tmp_path / "aptos_pkg.zip"
    img_bytes = _make_png_bytes(seed=11)
    with zipfile.ZipFile(arch_path, "w") as zf:
        zf.writestr("train.csv", "id_code,diagnosis\nrec_0,2\n")
        zf.writestr("train_images/rec_0.png", img_bytes)

    # Simulate interrupted import after 1 member
    interrupted = import_dataset_archive(
        "aptos",
        arch_path,
        dirs,
        interrupt_after_members=1,
    )
    assert interrupted.status == "interrupted_import"
    # Raw dir and preserved archive dir must stay clean; staging directory removed
    assert list(dirs.raw_by_dataset["aptos"].rglob("*")) == []
    assert list(dirs.temporary.iterdir()) == []

    # Legitimate import succeeds and preserves original archive untouched
    ok = import_dataset_archive("aptos", arch_path, dirs)
    assert ok.status == "imported"
    assert ok.extracted_files_count == 2
    assert Path(ok.preserved_archive_path or "").is_file()
    raw_img = dirs.raw_by_dataset["aptos"] / "train_images" / "rec_0.png"
    assert raw_img.read_bytes() == img_bytes

    # Second import without allow_overwrite=True is blocked cleanly
    blocked = import_dataset_archive("aptos", arch_path, dirs, allow_overwrite=False)
    assert blocked.status == "overwrite_blocked"
    assert raw_img.read_bytes() == img_bytes


def test_full_archive_to_audit_checksum_immutability_and_cross_dataset_duplicates(tmp_path: Path):
    """
    Exercise real-layout archive import -> inspection -> raw checksum verification -> preprocessing ->
    cross-dataset duplicate detection across two distinct datasets using tiny test fixtures.
    """
    mgr = DatasetDirectoryManager(str(tmp_path / "ds"))
    dirs = mgr.ensure_structure()

    shared_bytes = _make_png_bytes(size=(160, 120), seed=99)
    unique_aptos = _make_png_bytes(size=(200, 150), seed=100)

    # Build APTOS-like archive
    aptos_zip = tmp_path / "aptos_mock_layout.zip"
    with zipfile.ZipFile(aptos_zip, "w") as zf:
        zf.writestr("train.csv", "id_code,diagnosis\na1,0\na2,2\nmissing_ref,4\n")
        zf.writestr("train_images/a1.png", shared_bytes)
        zf.writestr("train_images/a2.png", unique_aptos)

    # Build IDRiD-like archive containing the EXACT duplicate shared_bytes image under another name
    idrid_zip = tmp_path / "idrid_mock_layout.zip"
    with zipfile.ZipFile(idrid_zip, "w") as zf:
        zf.writestr("Disease Grading.csv", "Image name,Retinopathy grade\nIDRiD_001,1\n")
        zf.writestr("images/IDRiD_001.png", shared_bytes)

    assert import_dataset_archive("aptos", aptos_zip, dirs).status == "imported"
    assert import_dataset_archive("idrid", idrid_zip, dirs).status == "imported"

    inspector = DatasetInspector()
    aptos_items = load_aptos_items(dirs.raw_by_dataset["aptos"])
    idrid_items = load_idrid_items(dirs.raw_by_dataset["idrid"])

    aptos_recs, aptos_sum = inspector.inspect_dataset(
        "aptos", dirs.raw_by_dataset["aptos"], aptos_items, dirs.manifests, dirs.rejected
    )
    inspector.inspect_dataset(
        "idrid", dirs.raw_by_dataset["idrid"], idrid_items, dirs.manifests, dirs.rejected
    )
    assert aptos_sum.accepted_count == 2
    assert aptos_sum.missing_image_count == 1

    # Reversible preprocessing into processed/ must preserve raw bytes identically
    prep = DatasetPreprocessor(PreprocessingConfig(target_size=(128, 128)))
    prep_recs, _ = prep.run(
        "aptos", aptos_recs, dirs.raw_by_dataset["aptos"], dirs.processed / "aptos", dirs.manifests
    )
    assert len(prep_recs) == 2

    checksum_check = verify_raw_checksums_unchanged(
        dirs.raw_by_dataset["aptos"], dirs.manifests / "aptos_manifest.jsonl"
    )
    assert checksum_check["all_unchanged"] is True
    assert checksum_check["checked_files"] == 2

    # Cross-dataset quality audit catches the exact SHA-256 overlap across aptos and idrid
    quality = inspect_cross_dataset_quality(dirs)
    assert quality["sufficient_for_model_development"] is True
    assert set(quality["datasets_inspected"]) == {"aptos", "idrid"}
    assert len(quality["cross_dataset_exact_duplicates"]) == 1
    assert set(quality["cross_dataset_exact_duplicates"][0]["datasets"]) == {"aptos", "idrid"}

    readiness = check_dataset_acquisition_readiness(dirs)
    csv_out, json_out = export_phase6_reports(
        dirs.reports / "p6_inv.csv", dirs.reports / "p6_sum.json", quality, readiness
    )
    assert csv_out.is_file() and json_out.is_file()
    summary = json.loads(json_out.read_text(encoding="utf-8"))
    assert summary["dr_development_labeled_images_verified"] == 3


def test_messidor2_and_drive_separation_rules_in_quality_audit(tmp_path: Path):
    """
    DRIVE vessel masks and Messidor-2 external evaluation images alone must NEVER trigger
    DR model development readiness (`sufficient_for_model_development == False`).
    """
    mgr = DatasetDirectoryManager(str(tmp_path / "ds"))
    dirs = mgr.ensure_structure()

    # Populate DRIVE archive only (non_dr_task)
    drive_zip = tmp_path / "drive_layout.zip"
    with zipfile.ZipFile(drive_zip, "w") as zf:
        zf.writestr("training/images/21_training.png", _make_png_bytes(size=(100, 100), seed=5))
        zf.writestr("training/1st_manual/21_manual1.png", _make_png_bytes(size=(100, 100), seed=6))

    assert import_dataset_archive("drive", drive_zip, dirs).status == "imported"

    # Populate Messidor-2 archive with pairing only (external_eval, no commercial dev)
    m2_zip = tmp_path / "messidor2_layout.zip"
    with zipfile.ZipFile(m2_zip, "w") as zf:
        zf.writestr("IMAGES/e1.png", _make_png_bytes(size=(120, 90), seed=8))
        zf.writestr("IMAGES/e2.png", _make_png_bytes(size=(120, 90), seed=9))
        zf.writestr("messidor_data.csv", "primary,secondary\ne1.png,e2.png\n")
        zf.writestr(
            "messidor2_grades.csv",
            "image_id,adjudicated_dr_grade,adjudicated_gradable\ne1.png,1,1\ne2.png,0,1\n",
        )
    assert import_dataset_archive("messidor2", m2_zip, dirs).status == "imported"

    inspector = DatasetInspector()
    inspector.inspect_dataset(
        "drive", dirs.raw_by_dataset["drive"], load_drive_items(dirs.raw_by_dataset["drive"]), dirs.manifests, dirs.rejected,
        require_valid_label=False,
    )
    inspector.inspect_dataset(
        "messidor2", dirs.raw_by_dataset["messidor2"], load_messidor2_items(dirs.raw_by_dataset["messidor2"]), dirs.manifests, dirs.rejected,
    )

    quality = inspect_cross_dataset_quality(dirs)
    assert quality["per_dataset_metrics"]["messidor2"]["patient_level_split_verifiable"] is True
    assert quality["per_dataset_metrics"]["drive"]["label_distribution"] == {"non_dr_task": 1}
    # Neither DRIVE (segmentation) nor Messidor-2 (external non-commercial benchmark) counts as dev data
    assert quality["dr_development_labeled_images_verified"] == 0
    assert quality["sufficient_for_model_development"] is False


def test_aptos_five_class_layout_test_set_unlabeled_and_checksums(tmp_path: Path):
    """Verify APTOS 5-grade scheme, unlabeled test_images cataloging, original filename/label preservation, and checksums."""
    mgr = DatasetDirectoryManager(str(tmp_path / "aptos_unit"))
    dirs = mgr.ensure_structure()

    aptos_zip = tmp_path / "aptos_official_shape.zip"
    train_rows = ["id_code,diagnosis"]
    with zipfile.ZipFile(aptos_zip, "w") as zf:
        for grade in range(5):
            fname = f"train_sample_{grade}.png"
            zf.writestr(f"train_images/{fname}", _make_png_bytes(size=(160, 120), seed=20 + grade))
            train_rows.append(f"train_sample_{grade},{grade}")
        train_rows.append("missing_id,3")
        zf.writestr("train.csv", "\n".join(train_rows) + "\n")
        zf.writestr("test.csv", "id_code\ntest_sample_0\n")
        zf.writestr("test_images/test_sample_0.png", _make_png_bytes(size=(160, 120), seed=50))

    imp = import_dataset_archive("aptos", aptos_zip, dirs)
    assert imp.status == "imported"

    items = load_aptos_items(dirs.raw_by_dataset["aptos"])
    inspector = DatasetInspector()
    records, summary = inspector.inspect_dataset(
        "aptos", dirs.raw_by_dataset["aptos"], items, dirs.manifests, dirs.rejected, require_valid_label=True
    )

    assert summary.total_entries_inspected == 7
    assert summary.accepted_count == 5
    assert summary.missing_image_count == 1
    assert summary.missing_label_count == 1

    accepted_labels = {r.standardized_grade_numeric: r.standardized_label for r in records if r.validation_status == "accepted"}
    assert accepted_labels == {
        0: "NO_DR",
        1: "MILD_NPDR",
        2: "MODERATE_NPDR",
        3: "SEVERE_NPDR",
        4: "PDR",
    }
    test_rec = next(r for r in records if r.relative_path == "test_images/test_sample_0.png")
    assert test_rec.annotation_availability == "unlabeled_competition_test_set"
    assert test_rec.patient_identifier is None

    vchk = verify_raw_checksums_unchanged(
        dirs.raw_by_dataset["aptos"], dirs.manifests / "aptos_manifest.jsonl"
    )
    assert vchk["all_unchanged"] is True
    assert vchk["checked_files"] == 5
