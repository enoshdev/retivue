"""Phase 8 unit & integration tests for APTOS duplicate/conflict resolution, FOV cropping, preprocessing, and stratified group splitting."""

import csv
import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from data_pipeline.cleaning import analyze_and_clean_aptos_dataset, run_phase8_aptos_pipeline
from data_pipeline.directory_manager import DatasetDirectoryManager
from data_pipeline.importers import load_aptos_items
from data_pipeline.inspector import DatasetInspector
from data_pipeline.manifest import ManifestRecord
from data_pipeline.preprocessor import (
    DatasetPreprocessor,
    PreprocessingConfig,
    detect_retinal_fov_bbox,
)
from data_pipeline.split_planner import plan_stratified_group_train_val_split


def _make_retinal_phantom(
    size=(400, 300),
    border_left_right=60,
    fill_rgb=(165, 95, 55),
    marker_rgb=(250, 220, 120),
    mode="RGB",
) -> bytes:
    """Create a synthetic fundus circle with black camera borders and a bright peripheral optic-disc marker."""
    w, h = size
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    cx, cy = w // 2, h // 2
    radius = min((w - 2 * border_left_right) // 2, (h - 20) // 2)
    yy, xx = np.ogrid[:h, :w]
    circle_mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius**2

    # Subtle radial shading + fundus base color
    rng = np.random.default_rng(123)
    texture = rng.integers(-12, 13, size=(h, w, 3), dtype=np.int16)
    base = np.clip(np.array(fill_rgb, dtype=np.int16) + texture, 25, 240).astype(np.uint8)
    arr[circle_mask] = base[circle_mask]

    # Place peripheral optic disc marker near right inner rim of retina
    od_x = cx + int(radius * 0.78)
    od_mask = (xx - od_x) ** 2 + (yy - cy) ** 2 <= max(4, radius // 8) ** 2
    arr[od_mask & circle_mask] = np.array(marker_rgb, dtype=np.uint8)

    pil_img = Image.fromarray(arr, mode="RGB")
    if mode == "L":
        pil_img = pil_img.convert("L")
    elif mode == "RGBA":
        pil_img = pil_img.convert("RGBA")

    buf = io.BytesIO()
    pil_img.save(buf, format="PNG")
    return buf.getvalue()


def test_duplicate_conflict_quarantine_and_train_test_overlap(tmp_path: Path):
    """
    Verify:
    - Conflicting-label exact duplicates quarantine ALL occurrences without auto-picking a label.
    - Consistent-label duplicates keep deterministically sorted first representative & log extras.
    - Official test overlaps are documented with byte identity verified and excluded from eligible splits.
    """
    dirs = DatasetDirectoryManager(str(tmp_path / "ds")).ensure_structure()
    raw_dir = dirs.raw_by_dataset["aptos"]
    (raw_dir / "train_images").mkdir(parents=True, exist_ok=True)
    (raw_dir / "test_images").mkdir(parents=True, exist_ok=True)

    consistent_bytes = _make_retinal_phantom(fill_rgb=(170, 90, 50))
    conflict_bytes = _make_retinal_phantom(fill_rgb=(130, 80, 45))
    overlap_bytes = _make_retinal_phantom(fill_rgb=(190, 110, 65))
    unique_grade3 = _make_retinal_phantom(fill_rgb=(140, 75, 40))

    # Write files matching APTOS layout
    (raw_dir / "train_images" / "c_a.png").write_bytes(consistent_bytes)
    (raw_dir / "train_images" / "c_b.png").write_bytes(consistent_bytes)
    (raw_dir / "train_images" / "conf_1.png").write_bytes(conflict_bytes)
    (raw_dir / "train_images" / "conf_2.png").write_bytes(conflict_bytes)
    (raw_dir / "train_images" / "tr_ov.png").write_bytes(overlap_bytes)
    (raw_dir / "train_images" / "g3.png").write_bytes(unique_grade3)
    (raw_dir / "test_images" / "te_ov.png").write_bytes(overlap_bytes)

    (raw_dir / "train.csv").write_text(
        "id_code,diagnosis\n"
        "c_a,1\n"
        "c_b,1\n"
        "conf_1,2\n"
        "conf_2,4\n"
        "tr_ov,0\n"
        "g3,3\n",
        encoding="utf-8",
    )
    (raw_dir / "test.csv").write_text("id_code\nte_ov\n", encoding="utf-8")

    inspector = DatasetInspector()
    items = load_aptos_items(raw_dir)
    inspector.inspect_dataset("aptos", raw_dir, items, dirs.manifests, dirs.rejected, require_valid_label=True)

    clean = analyze_and_clean_aptos_dataset(raw_dir, dirs.manifests / "aptos_manifest.jsonl", dirs.reports)
    assert clean["raw_train_total"] == 6
    assert clean["raw_test_total"] == 1
    assert clean["consistent_duplicate_groups"] == 1
    assert clean["consistent_duplicates_excluded"] == 1
    assert clean["conflicting_duplicate_groups"] == 1
    assert clean["conflicting_images_quarantined"] == 2
    assert clean["eligible_labeled_train_images"] == 3  # c_a, g3, tr_ov (conf_1 & conf_2 quarantined, c_b excluded)
    assert clean["train_test_shared_unique_sha256_count"] == 1
    assert clean["train_test_overlap_pairs_count"] == 1

    # Verify quarantine CSV contains BOTH conflicting members and never picked a winner
    with open(clean["outputs"]["conflict_quarantine_csv"], "r", encoding="utf-8") as f:
        q_rows = list(csv.DictReader(f))
    assert {r["original_filename"] for r in q_rows} == {"conf_1.png", "conf_2.png"}
    assert all(r["byte_identical_verified"] == "True" for r in q_rows)

    # Verify overlap CSV documents byte-identical train/test match
    with open(clean["outputs"]["train_test_overlap_csv"], "r", encoding="utf-8") as f:
        o_rows = list(csv.DictReader(f))
    assert len(o_rows) == 1
    assert o_rows[0]["train_filename"] == "tr_ov.png"
    assert o_rows[0]["test_filename"] == "te_ov.png"
    assert o_rows[0]["byte_identical_verified"] == "True"


def test_fov_crop_tissue_preservation_quality_flags_and_determinism(tmp_path: Path):
    """
    Verify:
    - Retinal FOV crop trims dark side borders without removing bright peripheral optic disc tissue.
    - Blank, dark, bright, and corrupt images are flagged cleanly rather than silently accepted.
    - Grayscale & RGBA images convert cleanly to RGB.
    - Aspect ratio preserved inside consistent 128x128 output with deterministic SHA-256 across runs.
    """
    raw_dir = tmp_path / "raw"
    proc_a = tmp_path / "proc_a"
    proc_b = tmp_path / "proc_b"
    raw_dir.mkdir(parents=True)

    # 1. Valid wide retinal phantom with peripheral disc marker (255, 230, 120)
    phantom_bytes = _make_retinal_phantom(size=(440, 260), border_left_right=85)
    (raw_dir / "phantom.png").write_bytes(phantom_bytes)
    phantom_sha = hashlib.sha256(phantom_bytes).hexdigest()

    # 2. Grayscale and RGBA fundus phantoms
    (raw_dir / "gray.png").write_bytes(_make_retinal_phantom(size=(300, 200), border_left_right=40, mode="L"))
    (raw_dir / "rgba.png").write_bytes(_make_retinal_phantom(size=(300, 200), border_left_right=40, mode="RGBA"))

    # 3. Unusable dark / blown-out bright / blank / corrupt files
    dark_arr = np.full((200, 200, 3), 3, dtype=np.uint8)
    Image.fromarray(dark_arr).save(raw_dir / "dark.png")

    bright_arr = np.full((200, 200, 3), 253, dtype=np.uint8)
    Image.fromarray(bright_arr).save(raw_dir / "bright.png")

    corrupt_path = raw_dir / "corrupt.png"
    corrupt_path.write_bytes(b"\x89PNG\r\n\x1a\ncorrupt_truncated_bytes")

    cfg = PreprocessingConfig.phase8_aptos_preset(target_size=(128, 128), clahe_applied=False)
    prep = DatasetPreprocessor(cfg)

    pr_ok, arr_ok = prep.preprocess_single("aptos", "phantom.png", phantom_sha, raw_dir, proc_a)
    pr_ok_b, _ = prep.preprocess_single("aptos", "phantom.png", phantom_sha, raw_dir, proc_b)

    assert pr_ok.status == "processed"
    assert pr_ok.fov_crop_applied is True
    assert pr_ok.cropped_width < pr_ok.original_width  # trimmed 85px wide dark pillarboxes cleanly
    assert (pr_ok.processed_width, pr_ok.processed_height) == (128, 128)
    assert pr_ok.aspect_ratio_preserved is True
    assert pr_ok.interpolation_used == "INTER_AREA"
    # Tissue preservation check: bright optic disc marker (R>210, G>180) must remain inside processed crop!
    assert arr_ok is not None
    assert int(arr_ok[:, :, 0].max()) >= 210

    # Determinism check: identical processed SHA-256 across separate runs
    assert pr_ok.processed_sha256 == pr_ok_b.processed_sha256

    # Color mode safety
    pr_gray, _ = prep.preprocess_single("aptos", "gray.png", "g", raw_dir, proc_a)
    pr_rgba, _ = prep.preprocess_single("aptos", "rgba.png", "r", raw_dir, proc_a)
    assert pr_gray.status == "processed" and pr_gray.processed_mode == "RGB"
    assert pr_rgba.status == "processed" and pr_rgba.processed_mode == "RGB"

    # Unusable / corrupt images flagged cleanly (never silently accepted!)
    pr_dark, _ = prep.preprocess_single("aptos", "dark.png", "d", raw_dir, proc_a)
    pr_bright, _ = prep.preprocess_single("aptos", "bright.png", "b", raw_dir, proc_a)
    pr_corrupt, _ = prep.preprocess_single("aptos", "corrupt.png", "c", raw_dir, proc_a)
    pr_missing, _ = prep.preprocess_single("aptos", "missing.png", "m", raw_dir, proc_a)
    assert pr_dark.status == "flagged_quality"
    assert pr_bright.status == "flagged_quality"
    assert pr_corrupt.status == "decode_error"
    assert pr_missing.status == "missing_source"

    # Failed crop guard on tiny 10x10 dot inside huge 300x300 black frame
    dot_arr = np.zeros((300, 300, 3), dtype=np.uint8)
    dot_arr[145:155, 145:155] = 200
    bbox, _, err = detect_retinal_fov_bbox(dot_arr, cfg)
    assert bbox is None and "minimum" in (err or "").lower()


def test_stratified_group_split_reproducibility_and_end_to_end_phase8(tmp_path: Path):
    """
    Verify deterministic seed reproducibility, stratification across 5 classes,
    exact duplicate group integrity, official test exclusion, raw immutability,
    and full end-to-end Phase 8 reconciliation.
    """
    dirs = DatasetDirectoryManager(str(tmp_path / "p8_e2e")).ensure_structure()
    raw_dir = dirs.raw_by_dataset["aptos"]
    (raw_dir / "train_images").mkdir(parents=True, exist_ok=True)
    (raw_dir / "test_images").mkdir(parents=True, exist_ok=True)

    rows = ["id_code,diagnosis"]
    raw_hashes = {}
    # 5 images per DR class (0..4) -> 25 distinct eligible + 1 duplicate conflict pair + 1 unusable dark + 1 test
    for grade in range(5):
        for k in range(5):
            fname = f"cls{grade}_{k}.png"
            data = _make_retinal_phantom(
                size=(360, 240) if k % 2 == 0 else (260, 260),
                border_left_right=40 if k % 2 == 0 else 15,
                fill_rgb=(120 + grade * 12 + k * 4, 70 + grade * 8 + k * 2, 40 + k * 3),
            )
            p = raw_dir / "train_images" / fname
            p.write_bytes(data)
            raw_hashes[fname] = hashlib.sha256(data).hexdigest()
            rows.append(f"cls{grade}_{k},{grade}")

    # Conflicting duplicate pair
    conf_bytes = _make_retinal_phantom(fill_rgb=(150, 85, 50))
    (raw_dir / "train_images" / "cf1.png").write_bytes(conf_bytes)
    (raw_dir / "train_images" / "cf2.png").write_bytes(conf_bytes)
    rows.extend(["cf1,0", "cf2,4"])

    # Dark unusable image (valid PNG, valid label, must be flagged during Phase 8 preprocessing)
    Image.fromarray(np.full((180, 180, 3), 2, dtype=np.uint8)).save(raw_dir / "train_images" / "too_dark.png")
    rows.append("too_dark,2")

    # Official unlabeled test image
    (raw_dir / "test_images" / "t0.png").write_bytes(conf_bytes)
    (raw_dir / "train.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    (raw_dir / "test.csv").write_text("id_code\nt0\n", encoding="utf-8")

    inspector = DatasetInspector()
    inspector.inspect_dataset(
        "aptos", raw_dir, load_aptos_items(raw_dir), dirs.manifests, dirs.rejected, require_valid_label=True
    )

    out1 = run_phase8_aptos_pipeline(dirs=dirs, target_size=128, seed=42, verify_byte_identity=True)
    split_csv_1 = (dirs.reports / "phase_8_split_manifest.csv").read_text(encoding="utf-8")

    # Second deterministic run with same seed must reproduce identical split manifest
    out2 = run_phase8_aptos_pipeline(dirs=dirs, target_size=128, seed=42, verify_byte_identity=True)
    split_csv_2 = (dirs.reports / "phase_8_split_manifest.csv").read_text(encoding="utf-8")
    assert split_csv_1 == split_csv_2

    ss = out1["split_summary"]
    assert ss["total_eligible_images"] == 25  # cf1/cf2 quarantined, too_dark flagged, t0 excluded
    assert ss["train_count"] == 20
    assert ss["val_count"] == 5
    # Exact 1 validation image per class with 5 images/class at 0.20 ratio
    assert all(cnt == 1 for cnt in ss["class_distribution_by_split"]["val"].values())
    assert ss["exact_sha256_overlap_between_train_and_val"] == 0
    assert ss["official_test_images_included"] == 0
    assert ss["patient_level_split_verified"] is False
    assert ss["clinically_independent_split_guaranteed"] is False
    assert out1["raw_checksum_audit"]["all_unchanged"] is True
    assert out1["cleaning_summary"]["conflicting_images_quarantined"] == 2
    assert ss["flagged_preprocessing_count"] == 1

    # Confirm raw files untouched byte-for-byte
    for fname, expected_sha in raw_hashes.items():
        cur_sha = hashlib.sha256((raw_dir / "train_images" / fname).read_bytes()).hexdigest()
        assert cur_sha == expected_sha

    # Also test refusal if an official test record is passed directly to split planner
    bad_rec = ManifestRecord(
        dataset_name="aptos",
        original_filename="t0.png",
        relative_path="test_images/t0.png",
        file_extension=".png",
        detected_media_type="image/png",
        file_size_bytes=100,
        width=128,
        height=128,
        channels=3,
        sha256_checksum="abc",
        perceptual_hash="0" * 16,
        raw_label="0",
        standardized_label="NO_DR",
        standardized_grade_numeric=0,
        label_mapping_status="mapped",
        label_mapping_rationale="test",
        annotation_availability="unlabeled",
        patient_identifier=None,
        patient_id_limitation_note="none",
        import_timestamp="now",
        validation_status="accepted",
        rejection_reason=None,
    )
    with pytest.raises(ValueError, match="Official test image"):
        plan_stratified_group_train_val_split([bad_rec], "aptos", dirs.reports)
