"""Fast isolated unit and integration tests for Phase 9 backend/ai training, evaluation & inference modules."""

import hashlib
import io
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from ai.checkpoint import save_checkpoint_with_provenance, verify_and_load_checkpoint
from ai.config import ModelDirectoryError, TrainingConfig, get_safe_model_root, resolve_torch_device
from ai.dataset import load_phase8_split_dataframe
from ai.inference import DRBaselinePredictor
from ai.metrics import compute_dr_evaluation_metrics
from ai.models import build_classifier_model, count_parameters, set_backbone_trainable
from ai.train import compute_train_loss_weights, run_training_experiment


def _make_retinal_png(size=(128, 128), fill=(160, 85, 45), seed: int = 7) -> bytes:
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


def test_model_root_boundaries_and_device_resolution(tmp_path: Path):
    """MODEL_ROOT rejects repo/clinical overlaps and device resolver falls back safely."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    with pytest.raises(ModelDirectoryError):
        get_safe_model_root(str(repo_root / "models"))
    with pytest.raises(ModelDirectoryError):
        get_safe_model_root(str(repo_root / "public" / "models"))

    safe_root = get_safe_model_root(str(tmp_path / "isolated_models"))
    assert (safe_root / "experiments").is_dir()

    cpu_info = resolve_torch_device("cpu")
    assert cpu_info["device"] == "cpu"
    auto_info = resolve_torch_device("auto")
    assert auto_info["device"] in ("cuda", "xpu", "cpu")


def test_dataset_guards_test_exclusion_overlap_and_missing_files(tmp_path: Path):
    """Split loader refuses test_images, train/val SHA leakage, and missing processed PNGs."""
    proc = tmp_path / "proc"
    proc.mkdir()
    (proc / "ok.png").write_bytes(_make_retinal_png())

    bad_test_csv = tmp_path / "bad_test.csv"
    bad_test_csv.write_text(
        "relative_path,processed_relative_path,sha256_checksum,standardized_grade_numeric,split\n"
        "test_images/t1.png,ok.png,abc,0,val\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Official APTOS test_images"):
        load_phase8_split_dataframe(bad_test_csv, proc)

    bad_leak_csv = tmp_path / "bad_leak.csv"
    bad_leak_csv.write_text(
        "relative_path,processed_relative_path,sha256_checksum,standardized_grade_numeric,split\n"
        "train_images/a.png,ok.png,same_sha,0,train\n"
        "train_images/b.png,ok.png,same_sha,0,val\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="leakage"):
        load_phase8_split_dataframe(bad_leak_csv, proc)

    missing_img_csv = tmp_path / "missing_img.csv"
    missing_img_csv.write_text(
        "relative_path,processed_relative_path,sha256_checksum,standardized_grade_numeric,split\n"
        "train_images/a.png,does_not_exist.png,sha1,0,train\n",
        encoding="utf-8",
    )
    with pytest.raises(FileNotFoundError):
        load_phase8_split_dataframe(missing_img_csv, proc)


def test_model_backbone_freeze_and_metrics_calculation():
    """Verify EfficientNet-B0 & ResNet-50 factories, layer freezing, imbalance weights, and metrics."""
    import torch

    m_eff = build_classifier_model("efficientnet_b0", num_classes=5, pretrained=False, dropout_p=0.2)
    tot_before, tr_before = count_parameters(m_eff)
    assert tot_before > 3_500_000 and tr_before == tot_before

    set_backbone_trainable(m_eff, "efficientnet_b0", trainable=False)
    _, tr_frozen = count_parameters(m_eff)
    assert tr_frozen < 20_000  # Only final linear layer trainable during Stage 1 warmup

    set_backbone_trainable(m_eff, "efficientnet_b0", trainable=True, unfreeze_from_block=5)
    _, tr_partial = count_parameters(m_eff)
    assert 3_000_000 < tr_partial < tot_before

    set_backbone_trainable(m_eff, "efficientnet_b0", trainable=True)
    _, tr_unfrozen = count_parameters(m_eff)
    assert tr_unfrozen == tot_before

    out = m_eff(torch.randn(2, 3, 128, 128))
    assert out.shape == (2, 5)

    m_res = build_classifier_model("resnet50", num_classes=5, pretrained=False)
    assert m_res(torch.randn(1, 3, 128, 128)).shape == (1, 5)

    w_eff = compute_train_loss_weights([0, 0, 0, 1, 2, 3, 4], "weighted_loss_effective")
    assert w_eff is not None and float(w_eff[3]) > float(w_eff[0])

    # Metrics calculation check
    y_true = np.array([0, 0, 1, 2, 3, 4, 3, 4])
    y_probs = np.array(
        [
            [0.85, 0.05, 0.05, 0.03, 0.02],
            [0.75, 0.15, 0.05, 0.03, 0.02],
            [0.10, 0.70, 0.10, 0.05, 0.05],
            [0.05, 0.15, 0.65, 0.10, 0.05],
            [0.05, 0.05, 0.15, 0.65, 0.10],
            [0.02, 0.03, 0.05, 0.10, 0.80],
            [0.60, 0.20, 0.10, 0.05, 0.05],  # False negative on Grade 3 -> pred 0!
            [0.02, 0.03, 0.05, 0.10, 0.80],
        ]
    )
    metrics = compute_dr_evaluation_metrics(y_true, y_probs)
    assert metrics["total_samples"] == 8
    assert metrics["clinical_safety_slices"]["severe_npdr_grade_3"]["false_negatives"] == 1
    assert metrics["clinical_safety_slices"]["pdr_grade_4"]["false_negatives"] == 0
    assert metrics["macro_ovr_roc_auc"] is not None
    assert len(metrics["confusion_matrix"]) == 5


def test_end_to_end_tiny_training_checkpoint_tamper_and_quality_gated_inference(tmp_path: Path):
    """Run tiny offline 2-epoch experiment, verify SHA-256 checkpoint integrity, and test ungradable gating."""
    proc_dir = tmp_path / "proc"
    model_root = tmp_path / "models"
    (proc_dir / "train_images").mkdir(parents=True)

    rows = [
        "dataset_name,relative_path,processed_relative_path,sha256_checksum,raw_label,standardized_label,standardized_grade_numeric,overlaps_official_test_sha256,split,split_basis,seed"
    ]
    labels_names = ["NO_DR", "MILD_NPDR", "MODERATE_NPDR", "SEVERE_NPDR", "PDR"]
    img_seed = 100
    for sp, count_per_cls in (("train", 2), ("val", 1)):
        for g in range(5):
            for k in range(count_per_cls):
                img_seed += 1
                fname = f"{sp}_{g}_{k}.png"
                png = _make_retinal_png(size=(96, 96), fill=(110 + g * 20, 60 + g * 12, 40), seed=img_seed)
                (proc_dir / "train_images" / fname).write_bytes(png)
                sha = hashlib.sha256(png).hexdigest()
                rows.append(
                    f"aptos,train_images/{fname},train_images/{fname},{sha},{g},{labels_names[g]},{g},False,{sp},test,42"
                )

    split_csv = tmp_path / "split_manifest.csv"
    split_csv.write_text("\n".join(rows) + "\n", encoding="utf-8")

    cfg = TrainingConfig(
        experiment_name="tiny_smoke",
        architecture="efficientnet_b0",
        pretrained=False,
        device_preference="cpu",
        input_size=96,
        batch_size=5,
        grad_accum_steps=1,
        warmup_epochs=1,
        max_epochs=2,
        early_stopping_patience=2,
        imbalance_strategy="weighted_sampler",
        augmentation_enabled=True,
    )
    res = run_training_experiment(
        config=cfg,
        split_manifest_csv=split_csv,
        processed_dataset_dir=proc_dir,
        model_root=model_root,
        run_id="smoke_run_01",
    )
    assert res["epochs_completed"] == 2
    ckpt_path = Path(res["best_checkpoint_path"])
    assert ckpt_path.is_file()
    assert Path(res["evaluation_artifacts"]["evaluation_report_json"]).is_file()
    assert Path(res["evaluation_artifacts"]["confusion_matrix_png"]).is_file()

    eval_data = json.loads(Path(res["evaluation_artifacts"]["evaluation_report_json"]).read_text(encoding="utf-8"))
    assert eval_data["patient_level_split_verified"] is False

    # Checkpoint SHA verification passes when untampered and fails if mismatch supplied
    verify_and_load_checkpoint(ckpt_path, expected_sha256=res["best_checkpoint_sha256"])
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        verify_and_load_checkpoint(ckpt_path, expected_sha256="0" * 64)

    # Quality-gated inference rejects dark/corrupt uploads cleanly instead of forcing DR grades
    predictor = DRBaselinePredictor(ckpt_path, device_preference="cpu")
    valid_pred = predictor.predict_from_bytes(_make_retinal_png(size=(160, 120)))
    assert valid_pred.gradable is True
    assert valid_pred.predicted_grade in (0, 1, 2, 3, 4)
    assert abs(sum(valid_pred.probabilities_by_class.values()) - 1.0) < 1e-3

    black_buf = io.BytesIO()
    Image.fromarray(np.zeros((160, 160, 3), dtype=np.uint8)).save(black_buf, format="PNG")
    ungradable_pred = predictor.predict_from_bytes(black_buf.getvalue())
    assert ungradable_pred.gradable is False
    assert ungradable_pred.quality_status == "ungradable_image_quality"
    assert ungradable_pred.predicted_grade is None
    assert ungradable_pred.uncertainty_review_required is True

    corrupt_pred = predictor.predict_from_bytes(b"not_an_image_bytes")
    assert corrupt_pred.gradable is False
    assert corrupt_pred.quality_status == "decode_error"
    assert corrupt_pred.predicted_grade is None
