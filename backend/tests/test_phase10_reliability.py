"""Isolated Phase 10 unit & integration tests for ai.reliability."""

import hashlib
import io
from pathlib import Path

import numpy as np
from PIL import Image
import pytest

from ai.config import TrainingConfig
from ai.inference import DRBaselinePredictor
from ai.reliability import (
    analyze_severe_and_pdr_false_negatives,
    assess_external_dataset_readiness,
    compute_bootstrap_confidence_intervals,
    compute_calibration_metrics,
    cross_validated_temperature_scaling,
    fit_temperature_scaling,
    run_synthetic_quality_stress_suite,
    simulate_uncertainty_triage,
    softmax_logits,
    validate_external_dataset_manifest,
)
from ai.train import run_training_experiment


def _make_retinal_png(size=(128, 128), fill=(160, 85, 45), seed: int = 11) -> bytes:
    w, h = size
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    cx, cy = w // 2, h // 2
    radius = min(w, h) // 2 - 4
    yy, xx = np.ogrid[:h, :w]
    mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius**2
    rng = np.random.default_rng(seed)
    noise = rng.integers(-15, 16, size=(h, w, 3), dtype=np.int16)
    base = np.clip(np.array(fill, dtype=np.int16) + noise, 20, 235).astype(np.uint8)
    arr[mask] = base[mask]
    buf = io.BytesIO()
    Image.fromarray(arr, mode="RGB").save(buf, format="PNG")
    return buf.getvalue()


def test_temperature_scaling_calibrates_overconfident_logits():
    rng = np.random.default_rng(42)
    n = 250
    y_true = np.repeat(np.arange(5), n // 5)
    # Construct deliberately overconfident logits (high temperature needed)
    base_logits = rng.normal(0.0, 1.8, size=(n, 5))
    for i, y in enumerate(y_true):
        base_logits[i, y] += 2.2
    overconfident_logits = base_logits * 3.5

    raw_probs = softmax_logits(overconfident_logits, temperature=1.0)
    raw_cal = compute_calibration_metrics(y_true, raw_probs)

    t_opt, nll_opt = fit_temperature_scaling(overconfident_logits, y_true)
    assert t_opt > 1.5
    assert nll_opt < raw_cal["nll"]

    cv_res = cross_validated_temperature_scaling(overconfident_logits, y_true, n_splits=5, seed=42)
    assert cv_res["oof_cv_calibration"]["ece"] < raw_cal["ece"]
    assert cv_res["oof_cv_calibration"]["nll"] < raw_cal["nll"]
    assert cv_res["oof_cv_calibration"]["brier_score"] <= raw_cal["brier_score"]
    # Rank-preserving calibration maintains top-1 argmax accuracy
    assert abs(cv_res["oof_cv_calibration"]["accuracy"] - raw_cal["accuracy"]) < 1e-6


def test_bootstrap_wilson_confidence_intervals_and_low_support_flag():
    y_true = np.array([0] * 60 + [1] * 15 + [2] * 30 + [3] * 10 + [4] * 15)
    rng = np.random.default_rng(7)
    logits = rng.normal(0.0, 1.0, size=(len(y_true), 5))
    for i, y in enumerate(y_true):
        logits[i, y] += 1.6
    probs = softmax_logits(logits, 1.0)

    ci = compute_bootstrap_confidence_intervals(y_true, probs, n_bootstrap=60, seed=42, low_support_threshold=50)
    assert ci["per_class_95ci"]["NO_DR"]["low_support_warning"] is False
    assert ci["per_class_95ci"]["SEVERE_NPDR"]["low_support_warning"] is True
    for cname, data in ci["per_class_95ci"].items():
        lo, hi = data["recall_wilson_95ci"]
        assert 0.0 <= lo <= data["recall_sensitivity"] <= hi <= 1.0
    for sk, sv in ci["summary_95ci"].items():
        if sv["bootstrap_95ci"]:
            lo, hi = sv["bootstrap_95ci"]
            assert lo <= sv["point"] <= hi or abs(lo - sv["point"]) < 0.05


def test_severe_pdr_false_negative_analysis_and_triage_rescue():
    sample_ids = [f"aptos_val_{i:04d}_deadbeef1234" for i in range(6)]
    y_true = np.array([0, 2, 3, 3, 4, 4])
    # Sample 2: Grade 3 missed as Grade 2 with borderline confidence & high P(G3+G4)
    # Sample 3: Grade 3 correctly classified
    # Sample 4: Grade 4 missed as Grade 2 with uncertain top2 margin
    # Sample 5: Grade 4 correctly classified
    probs = np.array(
        [
            [0.92, 0.04, 0.02, 0.01, 0.01],
            [0.05, 0.15, 0.72, 0.06, 0.02],
            [0.05, 0.10, 0.45, 0.35, 0.05],
            [0.02, 0.03, 0.10, 0.75, 0.10],
            [0.05, 0.10, 0.48, 0.22, 0.15],
            [0.01, 0.02, 0.04, 0.13, 0.80],
        ]
    )
    fn_res = analyze_severe_and_pdr_false_negatives(sample_ids, y_true, probs)
    assert fn_res["severe_npdr_breakdown"]["missed_vtdr_predicted_0_to_2_count"] == 1
    assert fn_res["pdr_breakdown"]["missed_vtdr_predicted_0_to_2_count"] == 1
    assert fn_res["vtdr_combined"]["vtdr_missed_as_0_to_2"] == 2
    assert all(".png" not in rec["sample_id"] for rec in fn_res["error_records"])

    triage = simulate_uncertainty_triage(y_true, probs)
    base = next(r for r in triage if r["policy_key"] == "no_triage_argmax_only")
    gate_a = next(r for r in triage if r["policy_key"] == "default_uncertainty_gate_conf060_margin015")
    assert base["vtdr_fn_remaining_unrescued"] == 2
    assert gate_a["vtdr_fn_rescued_by_escalation"] == 2
    assert gate_a["effective_vtdr_sensitivity_after_escalation"] == 1.0


def test_quality_stress_suite_and_external_dataset_guards(tmp_path: Path):
    # Create tiny local offline model checkpoint for testing stress suite + external manifest runner
    proc_dir = tmp_path / "proc"
    model_root = tmp_path / "models"
    (proc_dir / "train_images").mkdir(parents=True)

    rows = [
        "dataset_name,relative_path,processed_relative_path,sha256_checksum,raw_label,standardized_label,standardized_grade_numeric,overlaps_official_test_sha256,split,split_basis,seed"
    ]
    labels = ["NO_DR", "MILD_NPDR", "MODERATE_NPDR", "SEVERE_NPDR", "PDR"]
    seed_i = 500
    for sp, n_cls in (("train", 2), ("val", 1)):
        for g in range(5):
            for k in range(n_cls):
                seed_i += 1
                fn = f"{sp}_{g}_{k}.png"
                png = _make_retinal_png(size=(96, 96), fill=(110 + g * 20, 65 + g * 10, 45), seed=seed_i)
                (proc_dir / "train_images" / fn).write_bytes(png)
                sha = hashlib.sha256(png).hexdigest()
                rows.append(f"aptos,train_images/{fn},train_images/{fn},{sha},{g},{labels[g]},{g},False,{sp},test,42")

    split_csv = tmp_path / "split.csv"
    split_csv.write_text("\n".join(rows) + "\n", encoding="utf-8")

    res = run_training_experiment(
        config=TrainingConfig(
            experiment_name="phase10_test_smoke",
            pretrained=False,
            device_preference="cpu",
            input_size=96,
            batch_size=5,
            grad_accum_steps=1,
            warmup_epochs=1,
            max_epochs=2,
            early_stopping_patience=2,
        ),
        split_manifest_csv=split_csv,
        processed_dataset_dir=proc_dir,
        model_root=model_root,
        run_id="smoke_p10",
    )
    ckpt_path = Path(res["best_checkpoint_path"])
    predictor = DRBaselinePredictor(ckpt_path, device_preference="cpu")

    stress = run_synthetic_quality_stress_suite(predictor)
    by_key = {r["scenario_key"]: r for r in stress}

    for ungradable_key in ("pitch_black_image", "saturated_glare", "uniform_flat_grey", "tiny_peripheral_crop", "corrupted_non_image_bytes"):
        assert by_key[ungradable_key]["baseline_predictor_gradable"] is False
        assert by_key[ungradable_key]["baseline_forced_predicted_grade"] is None

    # Extended Phase 10 sharpness, contrast & obstruction diagnostics catch severe blur, haze, and half-frame block
    assert by_key["structured_synthetic_retina"]["phase10_sharpness_contrast_accepted"] is True
    assert by_key["severe_gaussian_defocus_blur"]["phase10_sharpness_contrast_accepted"] is False
    assert any("blur_low_sharpness" in r for r in by_key["severe_gaussian_defocus_blur"]["phase10_rejection_reasons"])
    assert by_key["washed_out_low_contrast_haze"]["phase10_sharpness_contrast_accepted"] is False
    assert by_key["half_frame_obstruction"]["phase10_sharpness_contrast_accepted"] is False

    # Readiness audit must flag empty folders honestly without fabricating datasets
    empty_ds_root = tmp_path / "empty_datasets"
    readiness = assess_external_dataset_readiness(empty_ds_root)
    ds_map = {d["dataset_key"]: d for d in readiness["datasets"]}
    assert ds_map["idrid"]["phase10_status"] == "BLOCKED_BY_MISSING_DATA_OR_AUTHORIZATION"
    assert ds_map["messidor2"]["phase10_status"] == "BLOCKED_BY_MISSING_DATA_OR_AUTHORIZATION"
    assert ds_map["drive"]["phase10_status"] == "UNSUITABLE_FOR_DR_GRADING_VESSEL_SEGMENTATION_ONLY"
    assert readiness["independent_external_datasets_available_on_disk"] == []

    # DRIVE must be refused for DR grading
    with pytest.raises(ValueError, match="vessel segmentation"):
        validate_external_dataset_manifest("drive", split_csv, proc_dir, ckpt_path)

    # Synthetic authorized external evaluation works cleanly & quarantines dark ungradable input
    ext_imgs = tmp_path / "ext_idrid"
    ext_imgs.mkdir()
    ok1 = _make_retinal_png(size=(160, 160), seed=901)
    ok2 = _make_retinal_png(size=(160, 160), fill=(180, 95, 50), seed=902)
    dark_buf = io.BytesIO()
    Image.fromarray(np.zeros((160, 160, 3), dtype=np.uint8)).save(dark_buf, format="PNG")
    (ext_imgs / "img1.png").write_bytes(ok1)
    (ext_imgs / "img2.png").write_bytes(ok2)
    (ext_imgs / "bad_dark.png").write_bytes(dark_buf.getvalue())

    ext_manifest = tmp_path / "ext_manifest.csv"
    ext_manifest.write_text(
        "sample_id,relative_path,dr_grade,patient_group_id\n"
        "ext_001,img1.png,0,pat_01\n"
        "ext_002,img2.png,2,pat_02\n"
        "ext_003,bad_dark.png,4,pat_03\n",
        encoding="utf-8",
    )
    ext_res = validate_external_dataset_manifest(
        dataset_key="idrid",
        manifest_csv=ext_manifest,
        images_root=ext_imgs,
        checkpoint_path=ckpt_path,
        expected_checkpoint_sha256=res["best_checkpoint_sha256"],
        temperature=1.25,
        device_preference="cpu",
    )
    assert ext_res["gradable_samples"] == 2
    assert ext_res["ungradable_rejected_samples"] == 1
    assert ext_res["patient_group_column_present"] is True
    assert ext_res["metrics"]["total_samples"] == 2

