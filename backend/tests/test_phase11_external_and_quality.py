"""Phase 11 unit and integration tests for hardened quality gating and external IDRiD ingestion/validation."""

import io
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
import pytest

from ai.checkpoint import save_checkpoint_with_provenance
from ai.config import TrainingConfig
from ai.inference import DRBaselinePredictor
from ai.models import build_classifier_model
from ai.reliability import (
    _make_synthetic_fundus_array,
    run_synthetic_quality_stress_suite,
    validate_external_dataset_manifest,
)
from data_pipeline.importers import load_idrid_items
from data_pipeline.preprocessor import (
    PreprocessingConfig,
    detect_retinal_fov_bbox,
)


def _save_dummy_checkpoint(tmp_path: Path, input_size: int = 128) -> tuple[Path, str]:
    model = build_classifier_model("efficientnet_b0", num_classes=5, pretrained=False, dropout_p=0.2)
    ckpt_path = tmp_path / "frozen_dummy_ckpt.pt"
    cfg = TrainingConfig(
        experiment_name="p11_quality_smoke",
        architecture="efficientnet_b0",
        pretrained=False,
        device_preference="cpu",
        input_size=input_size,
        num_classes=5,
        dropout_p=0.2,
    )
    meta = save_checkpoint_with_provenance(
        ckpt_path,
        model_state_dict=model.state_dict(),
        optimizer_state_dict=None,
        scheduler_state_dict=None,
        epoch=1,
        stage="smoke",
        best_metric_name="qwk",
        best_metric_value=0.5,
        config=cfg,
        split_manifest_sha256="0" * 64,
    )
    return ckpt_path, str(meta["checkpoint_sha256"])


def _to_png_bytes(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr, mode="RGB").save(buf, format="PNG")
    return buf.getvalue()


def test_idrid_importer_disambiguates_overlapping_train_and_test_stems(tmp_path: Path):
    """
    IDRiD reuses filenames like IDRiD_001.jpg across both `a. Training Set` and `b. Testing Set`.
    Verify load_idrid_items maps each CSV row strictly to its matching split folder.
    """
    train_dir = tmp_path / "B. Disease Grading" / "1. Original Images" / "a. Training Set"
    test_dir = tmp_path / "B. Disease Grading" / "1. Original Images" / "b. Testing Set"
    gt_dir = tmp_path / "B. Disease Grading" / "2. Groundtruths"
    train_dir.mkdir(parents=True)
    test_dir.mkdir(parents=True)
    gt_dir.mkdir(parents=True)

    tr_bytes = _to_png_bytes(_make_synthetic_fundus_array(128, seed=1))
    te_bytes = _to_png_bytes(_make_synthetic_fundus_array(128, seed=2))
    (train_dir / "IDRiD_001.jpg").write_bytes(tr_bytes)
    (test_dir / "IDRiD_001.jpg").write_bytes(te_bytes)

    (gt_dir / "a. IDRiD_Disease Grading_Training Labels.csv").write_text(
        "Image name,Retinopathy grade,Risk of macular edema \nIDRiD_001,1,0\n",
        encoding="utf-8",
    )
    (gt_dir / "b. IDRiD_Disease Grading_Testing Labels.csv").write_text(
        "Image name,Retinopathy grade,Risk of macular edema \nIDRiD_001,4,2\n",
        encoding="utf-8",
    )

    items = load_idrid_items(tmp_path)
    assert len(items) == 2
    by_label = {it.raw_label: it.relative_path for it in items}
    assert "a. Training Set/IDRiD_001.jpg" in by_label["1"]
    assert "b. Testing Set/IDRiD_001.jpg" in by_label["4"]


def test_hardened_quality_gate_rejects_blur_haze_obstruction_without_forcing_dr_grade(tmp_path: Path):
    """
    Phase 11 hardened DRBaselinePredictor must refuse severe blur, washed-out haze,
    and half-frame obstruction in addition to dark/glare/flat/tiny/corrupt payloads.
    """
    ckpt_path, sha = _save_dummy_checkpoint(tmp_path, input_size=128)
    predictor = DRBaselinePredictor(ckpt_path, expected_sha256=sha, device_preference="cpu")
    assert predictor.prep_config.extended_quality_check_enabled is True

    stress_rows = run_synthetic_quality_stress_suite(predictor)
    by_key = {r["scenario_key"]: r for r in stress_rows}

    ctrl = by_key["structured_synthetic_retina"]
    assert ctrl["baseline_predictor_gradable"] is True
    assert ctrl["baseline_quality_status"] == "gradable"
    assert ctrl["baseline_forced_predicted_grade"] in (0, 1, 2, 3, 4)

    blocked_keys = (
        "pitch_black_image",
        "saturated_glare",
        "uniform_flat_grey",
        "severe_gaussian_defocus_blur",
        "washed_out_low_contrast_haze",
        "half_frame_obstruction",
        "tiny_peripheral_crop",
        "corrupted_non_image_bytes",
    )
    for key in blocked_keys:
        row = by_key[key]
        assert row["baseline_predictor_gradable"] is False, f"{key} should be rejected by hardened gate"
        assert row["baseline_forced_predicted_grade"] is None, f"{key} must never force a DR grade"
        assert row["baseline_uncertainty_review_required"] is True
        expected_status = "decode_error" if key == "corrupted_non_image_bytes" else "ungradable_image_quality"
        assert row["baseline_quality_status"] == expected_status


def test_scale_invariant_quality_gate_on_high_res_and_rectangular_external_inputs(tmp_path: Path):
    """
    Large multi-camera images (1200x800, 1.5:1 aspect) downscaled to <=512px for sharpness check
    preserve valid acceptance while severely blurred high-res images still fail safely.
    """
    cfg_p11 = PreprocessingConfig.phase11_hardened_preset()
    base_hi = cv2.resize(_make_synthetic_fundus_array(400, seed=77), (1200, 800), interpolation=cv2.INTER_CUBIC)
    # Add crisp high-res vascular ridges
    cv2.line(base_hi, (780, 400), (320, 220), (85, 22, 16), 5)
    cv2.line(base_hi, (780, 400), (310, 590), (85, 22, 16), 5)

    bbox_ok, metrics_ok, reason_ok = detect_retinal_fov_bbox(base_hi, cfg_p11)
    assert bbox_ok is not None and reason_ok is None
    assert metrics_ok["laplacian_variance"] >= cfg_p11.min_laplacian_variance
    assert metrics_ok["local_rms_contrast"] >= cfg_p11.min_local_rms_contrast

    blur_hi = cv2.GaussianBlur(base_hi, (81, 81), sigmaX=32.0, sigmaY=32.0)
    bbox_bad, metrics_bad, reason_bad = detect_retinal_fov_bbox(blur_hi, cfg_p11)
    assert bbox_bad is None
    assert "blur_low_sharpness" in (reason_bad or "")
    assert metrics_bad["laplacian_variance"] < cfg_p11.min_laplacian_variance

    # External manifest validation enforces hardened gate and preserves rectangular letterboxing
    ckpt_path, sha = _save_dummy_checkpoint(tmp_path, input_size=128)
    ext_dir = tmp_path / "ext"
    ext_dir.mkdir()
    Image.fromarray(base_hi, mode="RGB").save(ext_dir / "sharp_rect.png")
    Image.fromarray(blur_hi, mode="RGB").save(ext_dir / "blur_rect.png")

    ext_csv = tmp_path / "ext_manifest.csv"
    ext_csv.write_text(
        "sample_id,relative_path,dr_grade\n"
        "s_sharp,sharp_rect.png,2\n"
        "s_blur,blur_rect.png,4\n",
        encoding="utf-8",
    )
    res = validate_external_dataset_manifest(
        dataset_key="idrid",
        manifest_csv=ext_csv,
        images_root=ext_dir,
        checkpoint_path=ckpt_path,
        expected_checkpoint_sha256=sha,
        device_preference="cpu",
    )
    assert res["total_manifest_samples"] == 2
    assert res["gradable_samples"] == 1
    assert res["ungradable_rejected_samples"] == 1
    assert res["ungradable_records"][0]["sample_id"] == "s_blur"
