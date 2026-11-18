"""
RETIVUE Phase 10: Model Reliability, Calibration, Uncertainty, False-Negative,
Quality Stress, Split Leakage & External Validation Suite.

Strictly isolated from clinical screening APIs (backend/app) and read-only toward
Phase 9 experiment checkpoints and Phase 8 datasets/manifests.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import cv2
import matplotlib
import numpy as np
import pandas as pd
import torch
from PIL import Image, ImageOps
from sklearn.model_selection import StratifiedKFold
from torch.utils.data import DataLoader

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from ai.checkpoint import collect_environment_metadata, compute_checkpoint_sha256, verify_and_load_checkpoint
from ai.config import CLASS_INDEX_TO_LABEL, IMAGENET_MEAN, IMAGENET_STD, resolve_torch_device
from ai.dataset import RetinalSplitDataset, load_phase8_split_dataframe
from ai.inference import DRBaselinePredictor
from ai.metrics import compute_dr_evaluation_metrics
from ai.models import build_classifier_model
from ai.transforms import build_retinal_transforms
from data_pipeline.preprocessor import (
    PreprocessingConfig,
    _resize_preserving_aspect_ratio_letterbox_cv,
    detect_retinal_fov_bbox,
    evaluate_extended_retinal_quality,
)
from data_pipeline.registry import VERIFIED_DATASET_REGISTRY


# ---------------------------------------------------------------------------
# A. Probability Calibration, Temperature Scaling & Uncertainty Quantification
# ---------------------------------------------------------------------------


def softmax_logits(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    """Compute numerically stable class probabilities for logits scaled by temperature > 0."""
    if temperature <= 0.0:
        raise ValueError(f"Temperature must be > 0, got {temperature}.")
    scaled = np.asarray(logits, dtype=np.float64) / float(temperature)
    shifted = scaled - np.max(scaled, axis=1, keepdims=True)
    exps = np.exp(shifted)
    return exps / np.sum(exps, axis=1, keepdims=True)


def _nll_from_probs(y_true: np.ndarray, probs: np.ndarray, eps: float = 1e-12) -> float:
    idx = np.arange(len(y_true))
    p_true = np.clip(probs[idx, y_true.astype(int)], eps, 1.0)
    return float(-np.mean(np.log(p_true)))


def _brier_from_probs(y_true: np.ndarray, probs: np.ndarray) -> float:
    num_classes = probs.shape[1]
    one_hot = np.eye(num_classes, dtype=np.float64)[y_true.astype(int)]
    return float(np.mean(np.sum((probs - one_hot) ** 2, axis=1)))


def compute_calibration_metrics(
    y_true: np.ndarray,
    probs: np.ndarray,
    n_bins: int = 15,
) -> Dict[str, Any]:
    """
    Compute formal probability calibration and prediction uncertainty diagnostics:
    - Negative Log-Likelihood (cross-entropy)
    - Multi-class Brier score in [0, 2]
    - Expected Calibration Error (ECE), Maximum Calibration Error (MCE), Overconfidence Error (OE)
    - Uniform confidence reliability bins
    - Predictive uncertainty summary (confidence, Shannon entropy, normalized entropy, top-2 margin)
    """
    y_arr = np.asarray(y_true, dtype=np.int64)
    p_arr = np.asarray(probs, dtype=np.float64)
    if len(y_arr) == 0 or len(y_arr) != len(p_arr):
        raise ValueError("y_true and probs must be non-empty with identical length.")

    p_arr = np.clip(p_arr, 1e-12, 1.0)
    p_arr = p_arr / np.sum(p_arr, axis=1, keepdims=True)

    n = float(len(y_arr))
    num_classes = p_arr.shape[1]
    confidences = np.max(p_arr, axis=1)
    preds = np.argmax(p_arr, axis=1)
    correct = (preds == y_arr).astype(np.float64)

    sorted_p = np.sort(p_arr, axis=1)
    top2_margin = sorted_p[:, -1] - sorted_p[:, -2] if num_classes >= 2 else confidences
    entropy = -np.sum(p_arr * np.log(p_arr), axis=1)
    max_entropy = math.log(num_classes) if num_classes > 1 else 1.0
    norm_entropy = entropy / max_entropy

    nll = _nll_from_probs(y_arr, p_arr)
    brier = _brier_from_probs(y_arr, p_arr)

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    mce = 0.0
    overconfidence_err = 0.0
    bins_summary: List[Dict[str, Any]] = []

    for b_idx in range(n_bins):
        low = float(bin_edges[b_idx])
        high = float(bin_edges[b_idx + 1])
        if b_idx == 0:
            in_bin = (confidences >= low) & (confidences <= high)
        else:
            in_bin = (confidences > low) & (confidences <= high)
        count = int(np.sum(in_bin))
        if count == 0:
            bins_summary.append(
                {
                    "bin_index": b_idx,
                    "bin_low": round(low, 4),
                    "bin_high": round(high, 4),
                    "count": 0,
                    "avg_confidence": None,
                    "avg_accuracy": None,
                    "abs_gap": None,
                }
            )
            continue

        avg_conf = float(np.mean(confidences[in_bin]))
        avg_acc = float(np.mean(correct[in_bin]))
        gap = abs(avg_conf - avg_acc)
        weight = count / n
        ece += weight * gap
        mce = max(mce, gap)
        if avg_conf > avg_acc:
            overconfidence_err += weight * (avg_conf - avg_acc)

        bins_summary.append(
            {
                "bin_index": b_idx,
                "bin_low": round(low, 4),
                "bin_high": round(high, 4),
                "count": count,
                "avg_confidence": round(avg_conf, 6),
                "avg_accuracy": round(avg_acc, 6),
                "abs_gap": round(gap, 6),
            }
        )

    correct_mask = correct == 1.0
    incorrect_mask = ~correct_mask

    return {
        "n_samples": int(len(y_arr)),
        "n_bins": n_bins,
        "accuracy": round(float(np.mean(correct)), 6),
        "nll": round(nll, 6),
        "brier_score": round(brier, 6),
        "ece": round(ece, 6),
        "mce": round(mce, 6),
        "overconfidence_error": round(overconfidence_err, 6),
        "uncertainty_summary": {
            "mean_confidence": round(float(np.mean(confidences)), 6),
            "median_confidence": round(float(np.median(confidences)), 6),
            "mean_entropy": round(float(np.mean(entropy)), 6),
            "mean_normalized_entropy": round(float(np.mean(norm_entropy)), 6),
            "mean_top2_margin": round(float(np.mean(top2_margin)), 6),
            "correct_mean_confidence": (
                round(float(np.mean(confidences[correct_mask])), 6) if np.any(correct_mask) else None
            ),
            "incorrect_mean_confidence": (
                round(float(np.mean(confidences[incorrect_mask])), 6) if np.any(incorrect_mask) else None
            ),
        },
        "bins": bins_summary,
    }


def fit_temperature_scaling(
    logits: np.ndarray,
    y_true: np.ndarray,
    min_temp: float = 0.05,
    max_temp: float = 10.0,
) -> Tuple[float, float]:
    """
    Fit scalar post-hoc temperature T > 0 minimizing validation NLL via golden-section search
    over log(T) (1D unimodal convex optimization; dependency-free and deterministic).
    Returns (optimal_temperature, optimal_nll).
    """
    logits_arr = np.asarray(logits, dtype=np.float64)
    y_arr = np.asarray(y_true, dtype=np.int64)

    def _loss(log_t: float) -> float:
        t = math.exp(log_t)
        probs = softmax_logits(logits_arr, temperature=t)
        return _nll_from_probs(y_arr, probs)

    # Coarse grid bracket + golden-section refinement
    grid = np.linspace(math.log(min_temp), math.log(max_temp), 96)
    losses = [_loss(float(x)) for x in grid]
    best_idx = int(np.argmin(losses))
    a = float(grid[max(0, best_idx - 1)])
    b = float(grid[min(len(grid) - 1, best_idx + 1)])

    phi = (math.sqrt(5.0) - 1.0) / 2.0
    c = b - phi * (b - a)
    d = a + phi * (b - a)
    fc, fd = _loss(c), _loss(d)
    for _ in range(55):
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - phi * (b - a)
            fc = _loss(c)
        else:
            a, c, fc = c, d, fd
            d = a + phi * (b - a)
            fd = _loss(d)
        if abs(b - a) < 1e-7:
            break

    best_log_t = 0.5 * (a + b)
    best_t = float(math.exp(best_log_t))
    best_nll = float(_loss(best_log_t))
    return round(best_t, 6), round(best_nll, 6)


def cross_validated_temperature_scaling(
    logits: np.ndarray,
    y_true: np.ndarray,
    n_splits: int = 5,
    seed: int = 42,
    n_bins: int = 15,
) -> Dict[str, Any]:
    """
    Evaluate temperature scaling via out-of-fold stratified cross-validation so ECE/NLL/Brier
    gains are measured without fitting and scoring on the exact same fold samples.
    Also fits full-split reference T_full (documented strictly as reference-only).
    """
    logits_arr = np.asarray(logits, dtype=np.float64)
    y_arr = np.asarray(y_true, dtype=np.int64)

    raw_probs = softmax_logits(logits_arr, temperature=1.0)
    raw_cal = compute_calibration_metrics(y_arr, raw_probs, n_bins=n_bins)

    skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    oof_probs = np.zeros_like(raw_probs)
    fold_temps: List[float] = []

    for train_idx, test_idx in skf.split(logits_arr, y_arr):
        t_fold, _ = fit_temperature_scaling(logits_arr[train_idx], y_arr[train_idx])
        fold_temps.append(t_fold)
        oof_probs[test_idx] = softmax_logits(logits_arr[test_idx], temperature=t_fold)

    oof_cal = compute_calibration_metrics(y_arr, oof_probs, n_bins=n_bins)
    t_full, _ = fit_temperature_scaling(logits_arr, y_arr)

    return {
        "raw_calibration": raw_cal,
        "oof_cv_calibration": oof_cal,
        "oof_cv_folds": n_splits,
        "oof_fold_temperatures": fold_temps,
        "mean_oof_temperature": round(float(np.mean(fold_temps)), 6),
        "std_oof_temperature": round(float(np.std(fold_temps)), 6),
        "full_split_reference_temperature": t_full,
        "raw_probs": raw_probs,
        "oof_calibrated_probs": oof_probs,
        "note": (
            "Out-of-fold CV on internal APTOS val prevents overfitting T to val labels, "
            "but true out-of-distribution calibration still requires an independent external dataset."
        ),
    }


# ---------------------------------------------------------------------------
# C. Per-Class Evaluation with Exact 95% Wilson & Stratified Bootstrap CIs
# ---------------------------------------------------------------------------


def wilson_ci(successes: int, total: int, z: float = 1.959963984540054) -> Tuple[float, float]:
    """Exact 95% Wilson score binomial confidence interval for sensitivity/specificity/precision."""
    if total <= 0:
        return 0.0, 0.0
    p = successes / total
    denom = 1.0 + (z * z) / total
    center = (p + (z * z) / (2.0 * total)) / denom
    half = (z * math.sqrt((p * (1.0 - p) + (z * z) / (4.0 * total)) / total)) / denom
    return round(max(0.0, center - half), 6), round(min(1.0, center + half), 6)


def compute_bootstrap_confidence_intervals(
    y_true: np.ndarray,
    y_probs: np.ndarray,
    n_bootstrap: int = 1000,
    seed: int = 42,
    low_support_threshold: int = 50,
) -> Dict[str, Any]:
    """
    Compute point metrics from ai.metrics.compute_dr_evaluation_metrics alongside
    Wilson 95% CIs (for exact binomial rates) and Stratified Bootstrap 95% CIs
    for F1, QWK, ROC-AUC, ECE, Brier, and NLL.
    """
    y_arr = np.asarray(y_true, dtype=np.int64)
    p_arr = np.asarray(y_probs, dtype=np.float64)
    point = compute_dr_evaluation_metrics(y_arr, p_arr, CLASS_INDEX_TO_LABEL)
    cal_point = compute_calibration_metrics(y_arr, p_arr)

    class_indices = {c: np.where(y_arr == c)[0] for c in sorted(CLASS_INDEX_TO_LABEL.keys()) if np.any(y_arr == c)}
    rng = np.random.default_rng(seed)

    boot_scalars: Dict[str, List[float]] = {
        "overall_accuracy": [],
        "macro_f1": [],
        "weighted_f1": [],
        "quadratic_weighted_kappa": [],
        "macro_ovr_roc_auc": [],
        "referable_dr_sensitivity": [],
        "referable_dr_specificity": [],
        "vtdr_sensitivity": [],
        "vtdr_specificity": [],
        "ece": [],
        "brier_score": [],
        "nll": [],
    }
    boot_cls_recall: Dict[str, List[float]] = {name: [] for name in CLASS_INDEX_TO_LABEL.values()}
    boot_cls_f1: Dict[str, List[float]] = {name: [] for name in CLASS_INDEX_TO_LABEL.values()}
    boot_cls_auc: Dict[str, List[float]] = {name: [] for name in CLASS_INDEX_TO_LABEL.values()}

    for _ in range(n_bootstrap):
        sampled_parts = [
            rng.choice(idxs, size=len(idxs), replace=True)
            for idxs in class_indices.values()
        ]
        b_idx = np.concatenate(sampled_parts)
        yb = y_arr[b_idx]
        pb = p_arr[b_idx]

        mb = compute_dr_evaluation_metrics(yb, pb, CLASS_INDEX_TO_LABEL)
        cb = compute_calibration_metrics(yb, pb)

        boot_scalars["overall_accuracy"].append(mb["overall_accuracy"])
        boot_scalars["macro_f1"].append(mb["macro_f1"])
        boot_scalars["weighted_f1"].append(mb["weighted_f1"])
        boot_scalars["quadratic_weighted_kappa"].append(mb["quadratic_weighted_kappa"])
        if mb["macro_ovr_roc_auc"] is not None:
            boot_scalars["macro_ovr_roc_auc"].append(mb["macro_ovr_roc_auc"])
        boot_scalars["referable_dr_sensitivity"].append(
            mb["clinical_safety_slices"]["referable_dr_grades_2_to_4"]["sensitivity_recall"]
        )
        boot_scalars["referable_dr_specificity"].append(
            mb["clinical_safety_slices"]["referable_dr_grades_2_to_4"]["specificity"]
        )
        boot_scalars["vtdr_sensitivity"].append(
            mb["clinical_safety_slices"]["vision_threatening_dr_grades_3_to_4"]["sensitivity_recall"]
        )
        boot_scalars["vtdr_specificity"].append(
            mb["clinical_safety_slices"]["vision_threatening_dr_grades_3_to_4"]["specificity"]
        )
        boot_scalars["ece"].append(cb["ece"])
        boot_scalars["brier_score"].append(cb["brier_score"])
        boot_scalars["nll"].append(cb["nll"])

        for cname in CLASS_INDEX_TO_LABEL.values():
            cm = mb["per_class"][cname]
            boot_cls_recall[cname].append(cm["recall_sensitivity"])
            boot_cls_f1[cname].append(cm["f1"])
            if cm["ovr_roc_auc"] is not None:
                boot_cls_auc[cname].append(cm["ovr_roc_auc"])

    def _pct_ci(vals: Sequence[float]) -> Optional[Tuple[float, float]]:
        if not vals:
            return None
        lo, hi = np.percentile(vals, [2.5, 97.5])
        return round(float(lo), 6), round(float(hi), 6)

    per_class_ci: Dict[str, Any] = {}
    total_n = len(y_arr)
    for cname, cdata in point["per_class"].items():
        sup = int(cdata["support"])
        tp = int(cdata["true_positives"])
        fp = int(cdata["false_positives"])
        fn = int(cdata["false_negatives"])
        tn = total_n - sup - fp

        rec_w_lo, rec_w_hi = wilson_ci(tp, sup)
        spec_w_lo, spec_w_hi = wilson_ci(tn, tn + fp)
        prec_w_lo, prec_w_hi = wilson_ci(tp, tp + fp)

        per_class_ci[cname] = {
            "grade": cdata["grade"],
            "support": sup,
            "low_support_warning": sup < low_support_threshold,
            "low_support_note": (
                f"Low sample count (n={sup} < {low_support_threshold}); estimate has wide uncertainty."
                if sup < low_support_threshold
                else None
            ),
            "recall_sensitivity": cdata["recall_sensitivity"],
            "recall_wilson_95ci": [rec_w_lo, rec_w_hi],
            "recall_bootstrap_95ci": list(_pct_ci(boot_cls_recall[cname]) or []),
            "specificity": cdata["specificity"],
            "specificity_wilson_95ci": [spec_w_lo, spec_w_hi],
            "precision": cdata["precision"],
            "precision_wilson_95ci": [prec_w_lo, prec_w_hi],
            "f1": cdata["f1"],
            "f1_bootstrap_95ci": list(_pct_ci(boot_cls_f1[cname]) or []),
            "ovr_roc_auc": cdata["ovr_roc_auc"],
            "ovr_roc_auc_bootstrap_95ci": list(_pct_ci(boot_cls_auc[cname]) or []),
        }

    ref_slice = point["clinical_safety_slices"]["referable_dr_grades_2_to_4"]
    vtdr_slice = point["clinical_safety_slices"]["vision_threatening_dr_grades_3_to_4"]

    return {
        "n_samples": total_n,
        "n_bootstrap": n_bootstrap,
        "seed": seed,
        "point_metrics": point,
        "summary_95ci": {
            "overall_accuracy": {
                "point": point["overall_accuracy"],
                "wilson_95ci": list(wilson_ci(point["ordinal_error_breakdown"]["exact_grade_matches"], total_n)),
                "bootstrap_95ci": list(_pct_ci(boot_scalars["overall_accuracy"]) or []),
            },
            "macro_f1": {"point": point["macro_f1"], "bootstrap_95ci": list(_pct_ci(boot_scalars["macro_f1"]) or [])},
            "weighted_f1": {"point": point["weighted_f1"], "bootstrap_95ci": list(_pct_ci(boot_scalars["weighted_f1"]) or [])},
            "quadratic_weighted_kappa": {
                "point": point["quadratic_weighted_kappa"],
                "bootstrap_95ci": list(_pct_ci(boot_scalars["quadratic_weighted_kappa"]) or []),
            },
            "macro_ovr_roc_auc": {
                "point": point["macro_ovr_roc_auc"],
                "bootstrap_95ci": list(_pct_ci(boot_scalars["macro_ovr_roc_auc"]) or []),
            },
            "referable_dr_sensitivity": {
                "point": ref_slice["sensitivity_recall"],
                "wilson_95ci": list(wilson_ci(ref_slice["true_positives"], ref_slice["support_positive"])),
                "bootstrap_95ci": list(_pct_ci(boot_scalars["referable_dr_sensitivity"]) or []),
            },
            "referable_dr_specificity": {
                "point": ref_slice["specificity"],
                "bootstrap_95ci": list(_pct_ci(boot_scalars["referable_dr_specificity"]) or []),
            },
            "vtdr_sensitivity": {
                "point": vtdr_slice["sensitivity_recall"],
                "wilson_95ci": list(wilson_ci(vtdr_slice["true_positives"], vtdr_slice["support_positive"])),
                "bootstrap_95ci": list(_pct_ci(boot_scalars["vtdr_sensitivity"]) or []),
            },
            "vtdr_specificity": {
                "point": vtdr_slice["specificity"],
                "bootstrap_95ci": list(_pct_ci(boot_scalars["vtdr_specificity"]) or []),
            },
            "ece": {"point": cal_point["ece"], "bootstrap_95ci": list(_pct_ci(boot_scalars["ece"]) or [])},
            "brier_score": {"point": cal_point["brier_score"], "bootstrap_95ci": list(_pct_ci(boot_scalars["brier_score"]) or [])},
            "nll": {"point": cal_point["nll"], "bootstrap_95ci": list(_pct_ci(boot_scalars["nll"]) or [])},
        },
        "per_class_95ci": per_class_ci,
    }


# ---------------------------------------------------------------------------
# D. Severe DR (Grade 3) & PDR (Grade 4) False-Negative & Uncertainty Triage
# ---------------------------------------------------------------------------


def anonymize_sample_id(split_name: str, row_idx: int, sha256_checksum: str) -> str:
    """Create strictly non-identifying anonymized sample ID using split index + truncated SHA-256."""
    return f"{split_name}_{row_idx:04d}_{sha256_checksum[:12]}"


def analyze_severe_and_pdr_false_negatives(
    sample_ids: Sequence[str],
    y_true: np.ndarray,
    y_probs_cal: np.ndarray,
    overlaps_test_sha: Optional[Sequence[bool]] = None,
) -> Dict[str, Any]:
    """
    Analyze Severe NPDR (Grade 3) and PDR (Grade 4) false-negative patterns using
    anonymized sample identifiers (no filenames or patient PII).
    """
    y_arr = np.asarray(y_true, dtype=np.int64)
    p_arr = np.asarray(y_probs_cal, dtype=np.float64)
    preds = np.argmax(p_arr, axis=1)
    sorted_p = np.sort(p_arr, axis=1)
    confidences = sorted_p[:, -1]
    margins = sorted_p[:, -1] - sorted_p[:, -2]
    entropy = -np.sum(np.clip(p_arr, 1e-12, 1.0) * np.log(np.clip(p_arr, 1e-12, 1.0)), axis=1)
    norm_entropy = entropy / math.log(p_arr.shape[1])

    overlaps = list(overlaps_test_sha) if overlaps_test_sha is not None else [False] * len(y_arr)

    def _grade_breakdown(target_grade: int) -> Dict[str, Any]:
        idxs = np.where(y_arr == target_grade)[0]
        pred_counts = {str(g): int(np.sum(preds[idxs] == g)) for g in range(5)}
        downgraded_exact = int(np.sum(preds[idxs] < target_grade))
        missed_vtdr = int(np.sum(preds[idxs] <= 2))
        missed_referable = int(np.sum(preds[idxs] <= 1))
        return {
            "true_grade": target_grade,
            "true_label": CLASS_INDEX_TO_LABEL[target_grade],
            "total_support": int(len(idxs)),
            "exact_tp": int(pred_counts[str(target_grade)]),
            "predicted_grade_distribution": pred_counts,
            "downgraded_below_true_grade_count": downgraded_exact,
            "missed_vtdr_predicted_0_to_2_count": missed_vtdr,
            "missed_referable_predicted_0_to_1_count": missed_referable,
        }

    fn_records: List[Dict[str, Any]] = []
    for i in range(len(y_arr)):
        yt = int(y_arr[i])
        yp = int(preds[i])
        if yt in (3, 4) and yp != yt:
            vtdr_prob = float(p_arr[i, 3] + p_arr[i, 4])
            fn_records.append(
                {
                    "sample_id": sample_ids[i],
                    "true_grade": yt,
                    "true_label": CLASS_INDEX_TO_LABEL[yt],
                    "predicted_grade": yp,
                    "predicted_label": CLASS_INDEX_TO_LABEL[yp],
                    "grade_deficit": yt - yp,
                    "missed_vtdr": yp <= 2,
                    "missed_referable": yp <= 1,
                    "confidence_max_prob": round(float(confidences[i]), 6),
                    "top2_margin": round(float(margins[i]), 6),
                    "normalized_entropy": round(float(norm_entropy[i]), 6),
                    "p_grade_3": round(float(p_arr[i, 3]), 6),
                    "p_grade_4": round(float(p_arr[i, 4]), 6),
                    "p_vtdr_sum_3_4": round(vtdr_prob, 6),
                    "overlaps_official_test_sha256": bool(overlaps[i]),
                    "uncertain_under_default_gate": bool(confidences[i] < 0.60 or margins[i] < 0.15),
                }
            )

    vtdr_mask = np.isin(y_arr, [3, 4])
    vtdr_fn_mask = vtdr_mask & (preds <= 2)
    ref_fn_in_vtdr = vtdr_mask & (preds <= 1)

    return {
        "severe_npdr_breakdown": _grade_breakdown(3),
        "pdr_breakdown": _grade_breakdown(4),
        "vtdr_combined": {
            "total_vtdr_support": int(np.sum(vtdr_mask)),
            "vtdr_detected_as_3_or_4": int(np.sum(vtdr_mask & (preds >= 3))),
            "vtdr_missed_as_0_to_2": int(np.sum(vtdr_fn_mask)),
            "vtdr_missed_as_non_referable_0_to_1": int(np.sum(ref_fn_in_vtdr)),
            "vtdr_fn_mean_confidence": (
                round(float(np.mean(confidences[vtdr_fn_mask])), 6) if np.any(vtdr_fn_mask) else None
            ),
            "vtdr_fn_mean_top2_margin": (
                round(float(np.mean(margins[vtdr_fn_mask])), 6) if np.any(vtdr_fn_mask) else None
            ),
            "vtdr_fn_mean_p_vtdr": (
                round(float(np.mean(p_arr[vtdr_fn_mask, 3] + p_arr[vtdr_fn_mask, 4])), 6)
                if np.any(vtdr_fn_mask)
                else None
            ),
        },
        "error_records": fn_records,
    }


def simulate_uncertainty_triage(
    y_true: np.ndarray,
    y_probs_cal: np.ndarray,
) -> List[Dict[str, Any]]:
    """
    Simulate uncertainty-based human-specialist referral/escalation strategies and measure:
    - Total clinician review burden (% of cohort flagged when prediction is non-VTDR <= 2)
    - Exact VTDR (Grades 3 & 4) false negatives rescued into manual review
    - Remaining unrescued VTDR false negatives and effective VTDR recall with triage
    """
    y_arr = np.asarray(y_true, dtype=np.int64)
    p_arr = np.asarray(y_probs_cal, dtype=np.float64)
    preds = np.argmax(p_arr, axis=1)
    sorted_p = np.sort(p_arr, axis=1)
    conf = sorted_p[:, -1]
    margin = sorted_p[:, -1] - sorted_p[:, -2]
    entropy = -np.sum(np.clip(p_arr, 1e-12, 1.0) * np.log(np.clip(p_arr, 1e-12, 1.0)), axis=1)
    norm_ent = entropy / math.log(p_arr.shape[1])
    p_vtdr = p_arr[:, 3] + p_arr[:, 4]

    n_total = len(y_arr)
    vtdr_true = np.isin(y_arr, [3, 4])
    n_vtdr = int(np.sum(vtdr_true))
    pred_non_vtdr = preds <= 2
    base_vtdr_fn = vtdr_true & pred_non_vtdr

    policies: List[Tuple[str, str, np.ndarray]] = [
        (
            "no_triage_argmax_only",
            "Baseline argmax only (no uncertainty escalation)",
            np.zeros(n_total, dtype=bool),
        ),
        (
            "default_uncertainty_gate_conf060_margin015",
            "Current predictor gate: max_prob < 0.60 OR top2_margin < 0.15",
            (conf < 0.60) | (margin < 0.15),
        ),
        (
            "stricter_uncertainty_gate_conf070_margin025",
            "Stricter gate: max_prob < 0.70 OR top2_margin < 0.25",
            (conf < 0.70) | (margin < 0.25),
        ),
        (
            "entropy_gate_norm_ent_gt_055",
            "High entropy gate: normalized_entropy > 0.55",
            norm_ent > 0.55,
        ),
        (
            "vtdr_risk_aware_p_vtdr_ge_015",
            "Safety-biased VTDR gate: pred <= 2 AND (P_cal(3+4) >= 0.15 OR conf < 0.60 OR margin < 0.15)",
            (p_vtdr >= 0.15) | (conf < 0.60) | (margin < 0.15),
        ),
        (
            "vtdr_risk_aware_p_vtdr_ge_010",
            "High-sensitivity VTDR gate: pred <= 2 AND (P_cal(3+4) >= 0.10 OR conf < 0.65)",
            (p_vtdr >= 0.10) | (conf < 0.65),
        ),
    ]

    results: List[Dict[str, Any]] = []
    for key, desc, flag_mask in policies:
        # Only predictions currently labeled <= 2 benefit from extra escalation beyond VTDR referral
        extra_escalated = pred_non_vtdr & flag_mask
        rescued = int(np.sum(base_vtdr_fn & flag_mask))
        remaining_fn = int(np.sum(base_vtdr_fn & ~flag_mask))
        detected_or_escalated = n_vtdr - remaining_fn
        severe_rem = int(np.sum((y_arr == 3) & pred_non_vtdr & ~flag_mask))
        pdr_rem = int(np.sum((y_arr == 4) & pred_non_vtdr & ~flag_mask))

        results.append(
            {
                "policy_key": key,
                "description": desc,
                "all_flagged_count": int(np.sum(flag_mask)),
                "all_flagged_pct": round(100.0 * float(np.sum(flag_mask)) / n_total, 2),
                "non_vtdr_escalated_count": int(np.sum(extra_escalated)),
                "non_vtdr_escalated_pct": round(100.0 * float(np.sum(extra_escalated)) / n_total, 2),
                "baseline_vtdr_fn": int(np.sum(base_vtdr_fn)),
                "vtdr_fn_rescued_by_escalation": rescued,
                "vtdr_fn_remaining_unrescued": remaining_fn,
                "severe_npdr_vtdr_fn_remaining": severe_rem,
                "pdr_vtdr_fn_remaining": pdr_rem,
                "effective_vtdr_sensitivity_after_escalation": round(detected_or_escalated / max(1, n_vtdr), 6),
            }
        )
    return results


# ---------------------------------------------------------------------------
# E. Image Quality Diagnostics & Ungradable Stress Suite
# ---------------------------------------------------------------------------


def compute_retinal_quality_diagnostics(
    rgb_arr: np.ndarray,
    config: Optional[PreprocessingConfig] = None,
    min_laplacian_variance: float = 15.0,
    min_local_rms_contrast: float = 1.0,
    max_fov_aspect_ratio: float = 1.65,
) -> Dict[str, Any]:
    """
    Inspect BOTH Phase 8 FOV/brightness gates AND extended Phase 10 sharpness/contrast/obstruction
    diagnostics on an RGB array without modifying Phase 8 preprocessing files.
    Default thresholds are anchored below real APTOS fundus percentiles (local RMS p01=1.03, aspect max=1.32).
    """
    cfg = config or PreprocessingConfig.phase8_aptos_preset()
    h, w = rgb_arr.shape[:2]
    gray = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2GRAY)
    global_std = float(np.std(rgb_arr))

    bbox, fov_metrics, phase8_reason = detect_retinal_fov_bbox(rgb_arr, cfg)
    if bbox is None:
        return {
            "phase8_accepted": False,
            "phase8_rejection_reason": phase8_reason,
            "phase10_extended_accepted": False,
            "phase10_extended_reasons": [phase8_reason or "phase8_fov_gate_rejected"],
            "global_std": round(global_std, 4),
            "fov_metrics": fov_metrics,
            "laplacian_variance": 0.0,
            "local_rms_contrast": 0.0,
            "fov_aspect_ratio": None,
            "fov_border_touch_sides": None,
        }

    x1, y1, x2, y2 = bbox
    roi_rgb = rgb_arr[y1:y2, x1:x2]
    lum = np.max(roi_rgb, axis=2)
    active_mask = lum > cfg.fov_threshold
    sat_frac = float(np.mean(lum[active_mask] >= 250)) if np.any(active_mask) else 0.0

    # Check if FOV bounding box touches >= 3 frame borders heavily truncated
    border_touches = sum([x1 == 0, y1 == 0, x2 >= w - 1, y2 >= h - 1])

    ext_metrics, ext_reasons = evaluate_extended_retinal_quality(
        roi_rgb,
        bg_thresh=cfg.fov_threshold,
        eval_max_dim=cfg.quality_eval_max_dim,
        min_laplacian_variance=min_laplacian_variance,
        min_local_rms_contrast=min_local_rms_contrast,
        max_fov_aspect_ratio=max_fov_aspect_ratio,
    )

    return {
        "phase8_accepted": True,
        "phase8_rejection_reason": None,
        "phase10_extended_accepted": len(ext_reasons) == 0,
        "phase10_extended_reasons": ext_reasons,
        "global_std": round(global_std, 4),
        "fov_metrics": fov_metrics,
        "saturated_fraction": round(sat_frac, 4),
        "laplacian_variance": ext_metrics["laplacian_variance"],
        "local_rms_contrast": ext_metrics["local_rms_contrast"],
        "fov_aspect_ratio": ext_metrics["fov_aspect_ratio"],
        "fov_border_touch_sides": int(border_touches),
    }


def _encode_png(arr: np.ndarray) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(arr, mode="RGB").save(buf, format="PNG")
    return buf.getvalue()


def _make_synthetic_fundus_array(size: int = 256, seed: int = 42) -> np.ndarray:
    """Create structured synthetic fundus-like disc with bright optic nerve & vascular arcs."""
    arr = np.zeros((size, size, 3), dtype=np.uint8)
    cy, cx = size // 2, size // 2
    radius = int(size * 0.44)
    yy, xx = np.ogrid[:size, :size]
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    mask = dist <= radius

    # Radial illumination shading + textured vessels
    shading = np.clip(1.0 - 0.35 * (dist / max(1, radius)) ** 2, 0.4, 1.0)
    rng = np.random.default_rng(seed)
    tex = rng.normal(0.0, 9.0, size=(size, size, 3))
    base = np.zeros((size, size, 3), dtype=np.float64)
    base[..., 0] = 175.0 * shading
    base[..., 1] = 88.0 * shading
    base[..., 2] = 42.0 * shading
    arr_f = np.clip(base + tex, 15, 240).astype(np.uint8)
    arr[mask] = arr_f[mask]

    # Add synthetic optic disc & vessel lines for crisp texture
    cv2.circle(arr, (int(cx + radius * 0.32), cy), max(8, size // 18), (225, 195, 130), -1)
    cv2.line(arr, (int(cx + radius * 0.32), cy), (int(cx - radius * 0.45), int(cy - radius * 0.35)), (95, 25, 18), 2)
    cv2.line(arr, (int(cx + radius * 0.32), cy), (int(cx - radius * 0.50), int(cy + radius * 0.30)), (95, 25, 18), 2)
    arr[~mask] = 0
    return arr


def run_synthetic_quality_stress_suite(predictor: DRBaselinePredictor) -> List[Dict[str, Any]]:
    """
    Stress-test current DRBaselinePredictor quality gates AND Phase 10 extended sharpness/contrast
    diagnostics across 9 deterministic degraded / ungradable inputs.
    """
    base = _make_synthetic_fundus_array(256, seed=42)

    # Smooth vignetted retina blurry enough to lose microaneurysm/vessel detail while retaining FOV std
    blurred = cv2.GaussianBlur(base, (31, 31), sigmaX=12.0, sigmaY=12.0)

    # Low-contrast milky haze inside circular FOV
    haze = base.astype(np.float64)
    yy, xx = np.ogrid[:256, :256]
    fov = ((xx - 128) ** 2 + (yy - 128) ** 2) <= (112 ** 2)
    haze_arr = np.zeros_like(base)
    haze_mean = np.array([150.0, 120.0, 105.0])
    haze_fov = np.clip(haze_mean + (haze - haze_mean) * 0.08, 0, 255).astype(np.uint8)
    haze_arr[fov] = haze_fov[fov]

    # Half-occluded frame (shutter / eyelid blocking upper 60% of retina)
    occluded = base.copy()
    occluded[:160, :] = 0

    # Tiny peripheral fragment below min_fov_area_ratio (0.12)
    tiny = np.zeros_like(base)
    cv2.circle(tiny, (128, 128), 32, (165, 85, 45), -1)

    scenarios: List[Tuple[str, str, bytes, Optional[np.ndarray]]] = [
        ("structured_synthetic_retina", "Synthetic sharp control inside circular FOV", _encode_png(base), base),
        ("pitch_black_image", "All-zero pitch black sensor failure", _encode_png(np.zeros_like(base)), np.zeros_like(base)),
        ("saturated_glare", "Overexposed white glare artifact (90% saturated)", _encode_png(np.full_like(base, 254)), np.full_like(base, 254)),
        ("uniform_flat_grey", "Uniform flat frame (zero contrast)", _encode_png(np.full_like(base, 128)), np.full_like(base, 128)),
        ("severe_gaussian_defocus_blur", "Severe Gaussian defocus blur (31x31, sigma=12)", _encode_png(blurred), blurred),
        ("washed_out_low_contrast_haze", "Media-opacity low-contrast haze inside circular FOV", _encode_png(haze_arr), haze_arr),
        ("half_frame_obstruction", "62% vertical frame black obstruction / eyelid", _encode_png(occluded), occluded),
        ("tiny_peripheral_crop", "Tiny retinal fragment (<12% frame area)", _encode_png(tiny), tiny),
        ("corrupted_non_image_bytes", "Corrupt truncated byte payload", b"not_a_valid_png_stream_0000", None),
    ]

    rows: List[Dict[str, Any]] = []
    for key, desc, payload, rgb_opt in scenarios:
        pred = predictor.predict_from_bytes(payload)
        diag = (
            compute_retinal_quality_diagnostics(rgb_opt)
            if rgb_opt is not None
            else {
                "phase8_accepted": False,
                "phase8_rejection_reason": "decode_error",
                "phase10_extended_accepted": False,
                "phase10_extended_reasons": ["decode_error"],
                "laplacian_variance": None,
                "local_rms_contrast": None,
                "fov_metrics": {},
            }
        )
        rows.append(
            {
                "scenario_key": key,
                "description": desc,
                "baseline_predictor_gradable": pred.gradable,
                "baseline_quality_status": pred.quality_status,
                "baseline_forced_predicted_grade": pred.predicted_grade,
                "baseline_uncertainty_review_required": pred.uncertainty_review_required,
                "baseline_confidence": round(pred.confidence_max_prob, 4) if pred.confidence_max_prob is not None else None,
                "baseline_quality_reason": pred.quality_reason,
                "baseline_uncertainty_reason": pred.uncertainty_reason,
                "phase8_fov_accepted": diag["phase8_accepted"],
                "phase10_sharpness_contrast_accepted": diag["phase10_extended_accepted"],
                "phase10_rejection_reasons": diag["phase10_extended_reasons"],
                "laplacian_variance": diag["laplacian_variance"],
                "local_rms_contrast": diag["local_rms_contrast"],
            }
        )
    return rows


# ---------------------------------------------------------------------------
# F. Patient-Level Independence, Test Overlap & Near-Duplicate Risk Audit
# ---------------------------------------------------------------------------


def audit_split_overlap_and_near_duplicates(
    split_df: pd.DataFrame,
    processed_dir: Path,
    val_df: pd.DataFrame,
    y_true_val: np.ndarray,
    y_probs_val: np.ndarray,
    near_dup_cosine_threshold: float = 0.990,
) -> Dict[str, Any]:
    """
    Quantify Phase 8 internal split leakage risks:
    1) Compare model metrics on val rows whose SHA-256 overlaps official APTOS test_images
       vs clean non-overlapping val rows.
    2) Compute normalized 16x16 structural cosine similarity across all train vs val processed
       fundus crops to estimate potential near-duplicate / fellow-eye pair prevalence.
    """
    overlap_flags = val_df["overlaps_official_test_sha256"].astype(str).str.lower().eq("true").to_numpy()
    clean_mask = ~overlap_flags

    subgroups: Dict[str, Any] = {}
    for label, mask in [
        ("all_val", np.ones(len(val_df), dtype=bool)),
        ("val_overlapping_official_test_sha256", overlap_flags),
        ("val_non_overlapping_official_test", clean_mask),
    ]:
        if np.any(mask):
            m = compute_dr_evaluation_metrics(y_true_val[mask], y_probs_val[mask], CLASS_INDEX_TO_LABEL)
            subgroups[label] = {
                "count": int(np.sum(mask)),
                "overall_accuracy": m["overall_accuracy"],
                "macro_f1": m["macro_f1"],
                "quadratic_weighted_kappa": m["quadratic_weighted_kappa"],
                "referable_sensitivity": m["clinical_safety_slices"]["referable_dr_grades_2_to_4"]["sensitivity_recall"],
                "vtdr_sensitivity": m["clinical_safety_slices"]["vision_threatening_dr_grades_3_to_4"]["sensitivity_recall"],
            }

    # Fast structural similarity matrix between train and val (16x16 zero-mean unit-norm vectors)
    train_df = split_df[split_df["split"] == "train"].reset_index(drop=True)

    def _structural_matrix(sub_df: pd.DataFrame) -> np.ndarray:
        vecs = np.zeros((len(sub_df), 256), dtype=np.float32)
        for idx, rel in enumerate(sub_df["processed_relative_path"].astype(str)):
            img_path = processed_dir / rel
            with Image.open(img_path) as im:
                g = np.asarray(im.convert("L").resize((16, 16), Image.Resampling.BILINEAR), dtype=np.float32).ravel()
            g -= np.mean(g)
            norm = float(np.linalg.norm(g))
            vecs[idx] = g / norm if norm > 1e-6 else g
        return vecs

    t_vecs = _structural_matrix(train_df)
    v_vecs = _structural_matrix(val_df)
    sim_matrix = np.matmul(v_vecs, t_vecs.T)  # [N_val, N_train]
    max_sim_per_val = np.max(sim_matrix, axis=1)
    best_train_pos = np.argmax(sim_matrix, axis=1)

    same_label_at_high_sim = int(
        np.sum(
            (max_sim_per_val >= near_dup_cosine_threshold)
            & (val_df["standardized_grade_numeric"].to_numpy() == train_df["standardized_grade_numeric"].to_numpy()[best_train_pos])
        )
    )

    return {
        "patient_identifiers_available": False,
        "patient_level_independence_verified": False,
        "train_count": int(len(train_df)),
        "val_count": int(len(val_df)),
        "val_official_test_overlap_count": int(np.sum(overlap_flags)),
        "val_subgroup_comparison": subgroups,
        "structural_near_duplicate_analysis": {
            "descriptor": "16x16 zero-mean L2-normalized grayscale cosine similarity (train vs val)",
            "cosine_ge_0_980_val_count": int(np.sum(max_sim_per_val >= 0.980)),
            "cosine_ge_0_990_val_count": int(np.sum(max_sim_per_val >= 0.990)),
            "cosine_ge_0_995_val_count": int(np.sum(max_sim_per_val >= 0.995)),
            "max_cross_split_cosine": round(float(np.max(max_sim_per_val)), 6),
            "median_nearest_train_cosine": round(float(np.median(max_sim_per_val)), 6),
            f"cosine_ge_{near_dup_cosine_threshold:.3f}_same_grade_count": same_label_at_high_sim,
        },
    }


# ---------------------------------------------------------------------------
# B. External Dataset Access Audit & Authorized Evaluation Runner
# ---------------------------------------------------------------------------


def assess_external_dataset_readiness(dataset_root: Path) -> Dict[str, Any]:
    """
    Verify on-disk existence, access gates, commercial-use rules, and suitability for
    IDRiD, Messidor-2, DRIVE, and APTOS without downloading or fabricating any data.
    """
    entries: List[Dict[str, Any]] = []
    for rec in VERIFIED_DATASET_REGISTRY:
        raw_dir = dataset_root / "raw" / rec.dataset_key
        arch_dir = dataset_root / "archives" / rec.dataset_key
        proc_dir = dataset_root / "processed" / rec.dataset_key
        raw_files = sum(1 for f in raw_dir.rglob("*") if f.is_file()) if raw_dir.exists() else 0
        arch_files = sum(1 for f in arch_dir.rglob("*") if f.is_file()) if arch_dir.exists() else 0
        proc_files = sum(1 for f in proc_dir.rglob("*") if f.is_file()) if proc_dir.exists() else 0

        if rec.dataset_key == "aptos":
            role_status = "INTERNAL_DEVELOPMENT_ONLY"
            ready = raw_files > 0 and proc_files > 0
            blocker = None
        elif rec.dataset_key == "drive":
            role_status = "UNSUITABLE_FOR_DR_GRADING_VESSEL_SEGMENTATION_ONLY"
            ready = False
            blocker = "DRIVE is a 40-image retinal blood vessel segmentation benchmark, not a 5-class DR grading dataset."
        elif raw_files == 0 and arch_files == 0:
            role_status = "BLOCKED_BY_MISSING_DATA_OR_AUTHORIZATION"
            ready = False
            blocker = f"Zero archives/raw files on disk ({rec.access_gate_details})"
        else:
            role_status = "AUTHORIZED_LOCAL_ARCHIVE_PRESENT"
            ready = True
            blocker = None

        entries.append(
            {
                "dataset_key": rec.dataset_key,
                "display_name": rec.display_name,
                "official_source_url": rec.official_source_url,
                "license_and_terms": rec.license_and_terms,
                "commercial_use_status": rec.commercial_use_status,
                "registration_or_application_required": rec.registration_or_application_required,
                "patient_identifiers_available": rec.patient_identifiers_available,
                "patient_level_separation_possible": rec.patient_level_separation_possible,
                "raw_files_on_disk": raw_files,
                "archive_files_on_disk": arch_files,
                "processed_files_on_disk": proc_files,
                "ready_for_external_dr_evaluation": ready,
                "phase10_status": role_status,
                "blocker_or_note": blocker,
            }
        )
    return {
        "dataset_root": str(dataset_root),
        "datasets": entries,
        "independent_external_validation_executed": False,
        "independent_external_datasets_available_on_disk": [
            e["dataset_key"] for e in entries if e["ready_for_external_dr_evaluation"] and e["dataset_key"] != "aptos"
        ],
    }


def validate_external_dataset_manifest(
    dataset_key: str,
    manifest_csv: Path,
    images_root: Path,
    checkpoint_path: Path,
    expected_checkpoint_sha256: Optional[str] = None,
    temperature: float = 1.0,
    device_preference: str = "auto",
) -> Dict[str, Any]:
    """
    Reusable evaluation entrypoint for future authorized external datasets (e.g., IDRiD or Messidor-2).
    Refuses DRIVE (vessel segmentation) and refuses unpopulated paths without fabricating metrics.
    Required CSV columns: sample_id, relative_path, dr_grade (0..4).
    Optional CSV column: patient_group_id (anonymized exam/patient group check).
    """
    ds_key = dataset_key.strip().lower()
    if ds_key == "drive":
        raise ValueError("DRIVE is a retinal vessel segmentation dataset and must not be used for 5-class DR grading.")
    if not manifest_csv.is_file():
        raise FileNotFoundError(f"External dataset manifest not found: {manifest_csv}")
    if not images_root.is_dir():
        raise FileNotFoundError(f"External dataset images root not found: {images_root}")

    df = pd.read_csv(manifest_csv)
    required_cols = {"sample_id", "relative_path", "dr_grade"}
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"External manifest missing required columns: {sorted(missing)}")

    # Verify files actually exist on disk before loading model
    missing_files = [str(images_root / str(p)) for p in df["relative_path"] if not (images_root / str(p)).is_file()]
    if missing_files:
        raise FileNotFoundError(f"External dataset missing {len(missing_files)} image files (first: {missing_files[0]}).")

    loaded = verify_and_load_checkpoint(checkpoint_path, expected_sha256=expected_checkpoint_sha256, map_location="cpu")
    ckpt_sha = compute_checkpoint_sha256(checkpoint_path)
    cfg = loaded.get("training_config", {})
    mean = tuple(loaded.get("norm_mean") or cfg.get("resolved_norm_mean") or IMAGENET_MEAN)
    std = tuple(loaded.get("norm_std") or cfg.get("resolved_norm_std") or IMAGENET_STD)
    input_size = int(loaded.get("input_size") or cfg.get("input_size", 512))
    arch = str(loaded.get("architecture") or cfg.get("architecture", "efficientnet_b0"))
    num_classes = int(loaded.get("num_classes") or cfg.get("num_classes", 5))
    dropout_p = float(loaded.get("dropout_p") or cfg.get("dropout_p", 0.3))

    dev_info = resolve_torch_device(device_preference)
    device = torch.device(dev_info["device"])
    model = build_classifier_model(architecture=arch, num_classes=num_classes, pretrained=False, dropout_p=dropout_p)
    model.load_state_dict(loaded["model_state_dict"])
    model.eval()
    model.to(device=device)

    tf = build_retinal_transforms(input_size=input_size, mean=mean, std=std, is_train=False, augmentation_enabled=False)
    pre_cfg = PreprocessingConfig.phase11_hardened_preset(
        target_size=(input_size, input_size),
        clahe_applied=False,
    )

    gradable_logits: List[np.ndarray] = []
    gradable_labels: List[int] = []
    ungradable_records: List[Dict[str, Any]] = []

    for row in df.to_dict(orient="records"):
        img_path = images_root / str(row["relative_path"])
        try:
            with Image.open(img_path) as im:
                im_rgb = ImageOps.exif_transpose(im).convert("RGB")
                rgb_arr = np.asarray(im_rgb, dtype=np.uint8)
        except Exception as exc:
            ungradable_records.append({"sample_id": str(row["sample_id"]), "reason": f"decode_error: {exc}"})
            continue

        bbox, _m, reject_reason = detect_retinal_fov_bbox(rgb_arr, pre_cfg)
        if bbox is None:
            ungradable_records.append({"sample_id": str(row["sample_id"]), "reason": reject_reason or "ungradable"})
            continue

        x1, y1, x2, y2 = bbox
        letterboxed, _, _, _ = _resize_preserving_aspect_ratio_letterbox_cv(
            rgb_arr[y1:y2, x1:x2],
            target_w=input_size,
            target_h=input_size,
            down_interp=pre_cfg.downscale_interpolation,
            up_interp=pre_cfg.upscale_interpolation,
        )
        tensor = tf(Image.fromarray(letterboxed, mode="RGB")).unsqueeze(0).to(device=device)
        with torch.no_grad():
            logit = model(tensor).cpu().numpy()[0]
        gradable_logits.append(logit)
        gradable_labels.append(int(row["dr_grade"]))

    result: Dict[str, Any] = {
        "dataset_key": ds_key,
        "checkpoint_sha256": ckpt_sha,
        "temperature_applied": float(temperature),
        "total_manifest_samples": int(len(df)),
        "gradable_samples": int(len(gradable_labels)),
        "ungradable_rejected_samples": int(len(ungradable_records)),
        "ungradable_records": ungradable_records,
        "patient_group_column_present": "patient_group_id" in df.columns,
    }
    if gradable_labels:
        logits_np = np.vstack(gradable_logits)
        y_np = np.asarray(gradable_labels, dtype=np.int64)
        probs_np = softmax_logits(logits_np, temperature=temperature)
        result["metrics"] = compute_dr_evaluation_metrics(y_np, probs_np, CLASS_INDEX_TO_LABEL)
        result["calibration"] = compute_calibration_metrics(y_np, probs_np)
    else:
        result["metrics"] = None
        result["calibration"] = None
    return result


# ---------------------------------------------------------------------------
# G. Deterministic Val Logit Extractor & Phase 10 Reliability Plotting
# ---------------------------------------------------------------------------


def extract_verified_val_logits(
    exp_dir: Path,
    split_manifest_csv: Path,
    processed_dir: Path,
    device_preference: str = "auto",
    batch_size: int = 16,
) -> Dict[str, Any]:
    """
    Cryptographically verify best_checkpoint.pt against best_checkpoint_meta.json,
    load without modifying Phase 9 artifacts, run deterministic val evaluation, verify exact
    reproduction against Phase 9 evaluation_report.json, and return raw logits & anonymized metadata.
    """
    best_pt = exp_dir / "best_checkpoint.pt"
    best_meta_path = exp_dir / "best_checkpoint_meta.json"
    eval_report_path = exp_dir / "evaluation_report.json"

    best_meta = json.loads(best_meta_path.read_text(encoding="utf-8"))
    expected_sha = best_meta.get("checkpoint_sha256")
    loaded = verify_and_load_checkpoint(best_pt, expected_sha256=expected_sha, map_location="cpu")
    actual_sha = compute_checkpoint_sha256(best_pt)

    val_df, manifest_sha = load_phase8_split_dataframe(
        split_manifest_csv=split_manifest_csv,
        processed_dataset_dir=processed_dir,
        split_filter="val",
        verify_files_exist=True,
    )
    val_df = val_df.reset_index(drop=True)

    cfg = loaded.get("training_config", {})
    mean = tuple(loaded.get("norm_mean") or cfg.get("resolved_norm_mean") or IMAGENET_MEAN)
    std = tuple(loaded.get("norm_std") or cfg.get("resolved_norm_std") or IMAGENET_STD)
    input_size = int(loaded.get("input_size") or cfg.get("input_size", 512))
    arch = str(loaded.get("architecture") or cfg.get("architecture", "efficientnet_b0"))
    num_classes = int(loaded.get("num_classes") or cfg.get("num_classes", 5))
    dropout_p = float(loaded.get("dropout_p") or cfg.get("dropout_p", 0.3))

    eval_tf = build_retinal_transforms(
        input_size=input_size, mean=mean, std=std, is_train=False, augmentation_enabled=False
    )
    dataset = RetinalSplitDataset(val_df, processed_dir, transform=eval_tf)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=0)

    dev_info = resolve_torch_device(device_preference)
    device = torch.device(dev_info["device"])
    use_cl = device.type == "cpu"

    model = build_classifier_model(architecture=arch, num_classes=num_classes, pretrained=False, dropout_p=dropout_p)
    model.load_state_dict(loaded["model_state_dict"])
    model.eval()
    if use_cl:
        model.to(device=device, memory_format=torch.channels_last)
    else:
        model.to(device=device)

    all_logits: List[np.ndarray] = []
    all_labels: List[np.ndarray] = []
    with torch.no_grad():
        for x, y, _idx in loader:
            x = x.to(device=device, memory_format=torch.channels_last) if use_cl else x.to(device=device)
            logits = model(x).cpu().numpy()
            all_logits.append(logits)
            all_labels.append(y.numpy())

    logits_np = np.vstack(all_logits)
    y_true_np = np.concatenate(all_labels)
    raw_probs_np = softmax_logits(logits_np, temperature=1.0)
    reproduced_metrics = compute_dr_evaluation_metrics(y_true_np, raw_probs_np, CLASS_INDEX_TO_LABEL)

    repro_diff: Dict[str, float] = {}
    if eval_report_path.is_file():
        recorded = json.loads(eval_report_path.read_text(encoding="utf-8")).get("metrics", {})
        for k in ("overall_accuracy", "macro_f1", "weighted_f1", "quadratic_weighted_kappa", "macro_ovr_roc_auc"):
            if k in recorded and recorded[k] is not None and reproduced_metrics.get(k) is not None:
                repro_diff[k] = round(abs(float(reproduced_metrics[k]) - float(recorded[k])), 8)

    sample_ids = [
        anonymize_sample_id("aptos_val", i, str(row["sha256_checksum"]))
        for i, row in val_df.iterrows()
    ]
    overlaps = val_df["overlaps_official_test_sha256"].astype(str).str.lower().eq("true").tolist()

    return {
        "exp_dir": str(exp_dir),
        "checkpoint_path": str(best_pt),
        "checkpoint_sha256": actual_sha,
        "checkpoint_sha256_verified": actual_sha == expected_sha,
        "checkpoint_epoch": best_meta.get("epoch"),
        "split_manifest_sha256": manifest_sha,
        "manifest_sha256_matches_meta": manifest_sha == best_meta.get("split_manifest_sha256"),
        "device_used": dev_info["device"],
        "environment": collect_environment_metadata(),
        "reproduction_abs_diff_vs_phase9": repro_diff,
        "reproduced_metrics": reproduced_metrics,
        "logits": logits_np,
        "y_true": y_true_np,
        "sample_ids": sample_ids,
        "overlaps_official_test_sha256": overlaps,
        "val_df": val_df,
    }


def plot_reliability_comparison(
    exp_results: Dict[str, Dict[str, Any]],
    output_path: Path,
) -> Path:
    """Plot Before vs Out-of-Fold Temperature-Scaled Reliability Diagrams across experiments."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    keys = list(exp_results.keys())
    fig, axes = plt.subplots(2, len(keys), figsize=(5.2 * len(keys), 8.2), squeeze=False)

    for col, k in enumerate(keys):
        cal_bundle = exp_results[k]["calibration"]
        raw_cal = cal_bundle["raw_calibration"]
        oof_cal = cal_bundle["oof_cv_calibration"]
        t_mean = cal_bundle["mean_oof_temperature"]

        for row, (title_prefix, cal_data, color) in enumerate(
            [
                ("Uncalibrated (T=1.0)", raw_cal, "#c0392b"),
                (f"OOF Temp-Scaled (T={t_mean:.2f})", oof_cal, "#1f6feb"),
            ]
        ):
            ax = axes[row, col]
            valid_bins = [b for b in cal_data["bins"] if b["count"] > 0]
            centers = [0.5 * (b["bin_low"] + b["bin_high"]) for b in valid_bins]
            accs = [b["avg_accuracy"] for b in valid_bins]
            confs = [b["avg_confidence"] for b in valid_bins]
            widths = [b["bin_high"] - b["bin_low"] - 0.006 for b in valid_bins]

            ax.plot([0, 1], [0, 1], "--", color="#555555", linewidth=1.2, label="Perfect Calibration")
            ax.bar(centers, accs, width=widths, alpha=0.65, color=color, edgecolor="#1b1f23", label="Observed Accuracy")
            for cx, acc, conf in zip(centers, accs, confs):
                ax.plot([cx, cx], [acc, conf], color="#f39c12", linewidth=1.6, alpha=0.85)
            ax.set_xlim(0.0, 1.0)
            ax.set_ylim(0.0, 1.0)
            ax.set_title(
                f"{k} | {title_prefix}\nECE={cal_data['ece']:.4f}, Brier={cal_data['brier_score']:.4f}, NLL={cal_data['nll']:.4f}",
                fontsize=9.5,
            )
            ax.set_xlabel("Mean Predicted Confidence")
            ax.set_ylabel("Empirical Accuracy")
            ax.grid(alpha=0.25)
            if col == 0:
                ax.legend(loc="upper left", fontsize=8)

    plt.suptitle("Phase 10 Probability Calibration: Before vs 5-Fold OOF Temperature Scaling (APTOS Val, n=700)", fontsize=12)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return output_path


def plot_metrics_confidence_intervals(
    ci_by_exp: Dict[str, Dict[str, Any]],
    output_path: Path,
) -> Path:
    """Plot per-class sensitivity & macro/VTDR metrics with 95% confidence interval error bars."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.4))

    class_names = [CLASS_INDEX_TO_LABEL[i] for i in range(5)]
    exp_keys = list(ci_by_exp.keys())
    colors = ["#2b6cb0", "#d97706", "#059669"]
    x = np.arange(len(class_names))
    w = 0.25

    for idx, k in enumerate(exp_keys):
        pc = ci_by_exp[k]["per_class_95ci"]
        pts = [pc[c]["recall_sensitivity"] for c in class_names]
        err_lo = [max(0.0, pt - pc[c]["recall_wilson_95ci"][0]) for pt, c in zip(pts, class_names)]
        err_hi = [max(0.0, pc[c]["recall_wilson_95ci"][1] - pt) for pt, c in zip(pts, class_names)]
        ax1.bar(x + (idx - 1) * w, pts, width=w, yerr=[err_lo, err_hi], capsize=3, color=colors[idx % len(colors)], alpha=0.85, label=k)

    ax1.set_xticks(x)
    ax1.set_xticklabels([f"{c}\n(n={ci_by_exp[exp_keys[0]]['per_class_95ci'][c]['support']})" for c in class_names], fontsize=8.5)
    ax1.set_ylim(0.0, 1.08)
    ax1.set_ylabel("Sensitivity / Recall (Wilson 95% CI)")
    ax1.set_title("Per-Class DR Sensitivity with 95% CIs (Note SEVERE n=35)")
    ax1.grid(axis="y", alpha=0.25)
    ax1.legend(fontsize=8.5)

    summary_keys = ["macro_f1", "quadratic_weighted_kappa", "referable_dr_sensitivity", "vtdr_sensitivity"]
    summary_labels = ["Macro F1", "QWK", "Referable Sens\n(2-4)", "VTDR Sens\n(3-4)"]
    x2 = np.arange(len(summary_keys))
    for idx, k in enumerate(exp_keys):
        sm = ci_by_exp[k]["summary_95ci"]
        pts = [sm[sk]["point"] for sk in summary_keys]
        err_lo = [max(0.0, pt - sm[sk]["bootstrap_95ci"][0]) for pt, sk in zip(pts, summary_keys)]
        err_hi = [max(0.0, sm[sk]["bootstrap_95ci"][1] - pt) for pt, sk in zip(pts, summary_keys)]
        ax2.bar(x2 + (idx - 1) * w, pts, width=w, yerr=[err_lo, err_hi], capsize=3, color=colors[idx % len(colors)], alpha=0.85, label=k)

    ax2.set_xticks(x2)
    ax2.set_xticklabels(summary_labels, fontsize=9)
    ax2.set_ylim(0.0, 1.08)
    ax2.set_ylabel("Score (Stratified Bootstrap 95% CI)")
    ax2.set_title("Clinical Safety & Agreement Slices with 95% CIs")
    ax2.grid(axis="y", alpha=0.25)
    ax2.legend(fontsize=8.5)

    plt.suptitle("Phase 10 Statistical Uncertainty & Per-Class Performance Bounds (APTOS Val, n=700)", fontsize=11.5)
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return output_path


def plot_uncertainty_triage_tradeoff(
    triage_by_exp: Dict[str, List[Dict[str, Any]]],
    output_path: Path,
) -> Path:
    """Plot clinician review burden (% escalated) vs effective VTDR sensitivity after uncertainty gating."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8.6, 5.2))
    colors = {"E0": "#2b6cb0", "E1": "#d97706", "E2": "#059669"}

    for k, rows in triage_by_exp.items():
        ordered = sorted(rows, key=lambda r: (r["non_vtdr_escalated_pct"], r["effective_vtdr_sensitivity_after_escalation"]))
        xs = [r["non_vtdr_escalated_pct"] for r in ordered]
        ys = [100.0 * r["effective_vtdr_sensitivity_after_escalation"] for r in ordered]
        ax.plot(xs, ys, marker="o", linewidth=2.0, color=colors.get(k, "#333333"), label=k)
        for r, xv, yv in zip(ordered, xs, ys):
            if r["policy_key"] in ("no_triage_argmax_only", "default_uncertainty_gate_conf060_margin015", "vtdr_risk_aware_p_vtdr_ge_010"):
                short = "Base" if "no_triage" in r["policy_key"] else ("DefaultGate" if "default" in r["policy_key"] else "VTDR>=0.10")
                ax.annotate(f"{short} ({yv:.1f}%)", (xv, yv), textcoords="offset points", xytext=(5, 4), fontsize=7.5)

    ax.set_xlabel("Additional Cohort Cases Escalated for Human Review (% of n=700)")
    ax.set_ylabel("Effective VTDR (Grades 3 & 4) Detection + Triage Rate (%)")
    ax.set_title("Phase 10 Uncertainty-Based Referral Simulation (OOF-Calibrated Probabilities)")
    ax.set_ylim(55.0, 102.0)
    ax.grid(alpha=0.25)
    ax.legend()
    plt.tight_layout()
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return output_path


def plot_quality_diagnostics_distribution(
    val_quality_df: pd.DataFrame,
    stress_rows: List[Dict[str, Any]],
    output_path: Path,
) -> Path:
    """Visualize sharpness (Laplacian variance) & local RMS contrast of APTOS val vs synthetic failures."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.5, 4.8))

    lap_vals = np.clip(val_quality_df["laplacian_variance"].to_numpy(), 0.0, 600.0)
    rms_vals = val_quality_df["local_rms_contrast"].to_numpy()

    ax1.hist(lap_vals, bins=35, color="#1f6feb", alpha=0.75, edgecolor="#1b1f23", label="APTOS Val (n=700)")
    ax1.axvline(15.0, color="#c0392b", linestyle="--", linewidth=1.6, label="Proposed Phase 10 Sharpness Floor (15.0)")
    blur_row = next((r for r in stress_rows if r["scenario_key"] == "severe_gaussian_defocus_blur"), None)
    if blur_row and blur_row["laplacian_variance"] is not None:
        ax1.axvline(blur_row["laplacian_variance"], color="#d97706", linestyle=":", linewidth=2.0, label=f"Gaussian Blur Stress ({blur_row['laplacian_variance']:.1f})")
    ax1.set_title("Active-FOV Sharpness (Laplacian Variance)")
    ax1.set_xlabel("Laplacian Variance (clipped at 600)")
    ax1.set_ylabel("Image Count")
    ax1.legend(fontsize=8)
    ax1.grid(alpha=0.25)

    ax2.hist(rms_vals, bins=35, color="#059669", alpha=0.75, edgecolor="#1b1f23", label="APTOS Val (n=700)")
    ax2.axvline(1.0, color="#c0392b", linestyle="--", linewidth=1.6, label="Calibrated Local RMS Floor (1.0)")
    haze_row = next((r for r in stress_rows if r["scenario_key"] == "washed_out_low_contrast_haze"), None)
    if haze_row and haze_row["local_rms_contrast"] is not None:
        ax2.axvline(haze_row["local_rms_contrast"], color="#d97706", linestyle=":", linewidth=2.0, label=f"Haze Stress ({haze_row['local_rms_contrast']:.1f})")
    ax2.set_title("Active-FOV Local 15x15 RMS Contrast")
    ax2.set_xlabel("Median Local RMS Contrast")
    ax2.set_ylabel("Image Count")
    ax2.legend(fontsize=8)
    ax2.grid(alpha=0.25)

    plt.suptitle("Phase 10 Image Quality Diagnostics: Clean APTOS Val vs Synthetic Ungradable Probes", fontsize=11.5)
    plt.tight_layout(rect=[0, 0, 1, 0.94])
    fig.savefig(output_path, dpi=160)
    plt.close(fig)
    return output_path


def _snapshot_experiment_hashes(experiments_dir: Path, exp_names: Sequence[str]) -> Dict[str, Dict[str, str]]:
    """Record read-only SHA-256 checksums of Phase 9 experiment files before & after Phase 10 audit."""
    tracked = ("best_checkpoint.pt", "best_checkpoint_meta.json", "last_checkpoint.pt", "run_manifest.json", "evaluation_report.json")
    snap: Dict[str, Dict[str, str]] = {}
    for name in exp_names:
        ed = experiments_dir / name
        snap[name] = {}
        for fn in tracked:
            fp = ed / fn
            if fp.is_file():
                snap[name][fn] = compute_checkpoint_sha256(fp)
    return snap


def run_phase10_reliability_audit(
    dataset_root: Path,
    model_root: Path,
    output_dir: Path,
    experiment_map: Optional[Dict[str, str]] = None,
    n_bootstrap: int = 1000,
    seed: int = 42,
    device_preference: str = "auto",
) -> Dict[str, Any]:
    """
    Execute the complete Phase 10 reliability audit across E0, E1, E2 without modifying any
    Phase 8 datasets or Phase 9 checkpoints/artifacts. Writes all outputs solely to output_dir.
    """
    exp_map = experiment_map or {
        "E0": "aptos_e0_unweighted",
        "E1": "aptos_e1_weighted_effective",
        "E2": "aptos_e2_weighted_sampler",
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    experiments_root = model_root / "experiments"
    if output_dir.resolve() == experiments_root.resolve() or experiments_root.resolve() in output_dir.resolve().parents:
        raise ValueError("Phase 10 output_dir must be strictly separate from Phase 9 experiments/ directory.")

    split_manifest_csv = dataset_root / "reports" / "phase_8_split_manifest.csv"
    processed_dir = dataset_root / "processed" / "aptos"
    full_split_df, manifest_sha = load_phase8_split_dataframe(
        split_manifest_csv=split_manifest_csv,
        processed_dataset_dir=processed_dir,
        split_filter=None,
        verify_files_exist=True,
    )

    pre_hashes = _snapshot_experiment_hashes(experiments_root, list(exp_map.values()))
    external_readiness = assess_external_dataset_readiness(dataset_root)

    exp_bundles: Dict[str, Dict[str, Any]] = {}
    ci_by_exp: Dict[str, Dict[str, Any]] = {}
    triage_by_exp: Dict[str, List[Dict[str, Any]]] = {}
    fn_by_exp: Dict[str, Dict[str, Any]] = {}
    overlap_by_exp: Dict[str, Any] = {}

    y_true_ref: Optional[np.ndarray] = None
    val_df_ref: Optional[pd.DataFrame] = None
    sample_ids_ref: Optional[List[str]] = None

    for short_key, folder_name in exp_map.items():
        ed = experiments_root / folder_name
        extracted = extract_verified_val_logits(
            exp_dir=ed,
            split_manifest_csv=split_manifest_csv,
            processed_dir=processed_dir,
            device_preference=device_preference,
        )
        logits = extracted["logits"]
        y_true = extracted["y_true"]
        sample_ids = extracted["sample_ids"]
        overlaps = extracted["overlaps_official_test_sha256"]
        if y_true_ref is None:
            y_true_ref = y_true
            val_df_ref = extracted["val_df"]
            sample_ids_ref = sample_ids

        cal = cross_validated_temperature_scaling(logits, y_true, n_splits=5, seed=seed, n_bins=15)
        raw_probs = cal["raw_probs"]
        oof_probs = cal["oof_calibrated_probs"]

        ci_res = compute_bootstrap_confidence_intervals(y_true, raw_probs, n_bootstrap=n_bootstrap, seed=seed)
        ci_by_exp[short_key] = ci_res

        fn_res = analyze_severe_and_pdr_false_negatives(sample_ids, y_true, oof_probs, overlaps_test_sha=overlaps)
        fn_by_exp[short_key] = fn_res
        pd.DataFrame(fn_res["error_records"]).to_csv(output_dir / f"{short_key.lower()}_severe_pdr_fn_anonymized.csv", index=False)

        triage_rows = simulate_uncertainty_triage(y_true, oof_probs)
        triage_by_exp[short_key] = triage_rows

        overlap_res = audit_split_overlap_and_near_duplicates(
            split_df=full_split_df,
            processed_dir=processed_dir,
            val_df=extracted["val_df"],
            y_true_val=y_true,
            y_probs_val=raw_probs,
        )
        overlap_by_exp[short_key] = overlap_res

        # Export anonymized Phase 10 validation table (raw & OOF-calibrated probs, zero raw filenames)
        oof_pred = np.argmax(oof_probs, axis=1)
        raw_pred = np.argmax(raw_probs, axis=1)
        out_df = pd.DataFrame(
            {
                "sample_id": sample_ids,
                "true_grade": y_true,
                "overlaps_official_test_sha256": overlaps,
                "raw_pred_grade": raw_pred,
                "oof_cal_pred_grade": oof_pred,
                "raw_max_prob": np.max(raw_probs, axis=1),
                "oof_cal_max_prob": np.max(oof_probs, axis=1),
            }
        )
        for g in range(5):
            out_df[f"logit_{g}"] = logits[:, g]
            out_df[f"oof_cal_prob_{g}"] = oof_probs[:, g]
        out_df.to_csv(output_dir / f"{short_key.lower()}_val_calibrated_anonymized.csv", index=False)

        exp_bundles[short_key] = {
            "run_folder": folder_name,
            "checkpoint_sha256": extracted["checkpoint_sha256"],
            "checkpoint_sha256_verified": extracted["checkpoint_sha256_verified"],
            "checkpoint_epoch": extracted["checkpoint_epoch"],
            "split_manifest_sha256": extracted["split_manifest_sha256"],
            "manifest_sha256_matches_meta": extracted["manifest_sha256_matches_meta"],
            "device_used": extracted["device_used"],
            "reproduction_abs_diff_vs_phase9": extracted["reproduction_abs_diff_vs_phase9"],
            "calibration": cal,
            "confidence_intervals": ci_res,
            "false_negative_analysis": fn_res,
            "uncertainty_triage": triage_rows,
            "overlap_and_leakage": overlap_res,
        }

    # Cross-model agreement on VTDR (Grades 3 & 4)
    assert y_true_ref is not None and val_df_ref is not None and sample_ids_ref is not None
    vtdr_idx = np.where(np.isin(y_true_ref, [3, 4]))[0]
    missed_sets: Dict[str, set] = {}
    for sk in exp_bundles:
        probs_oof = exp_bundles[sk]["calibration"]["oof_calibrated_probs"]
        preds_oof = np.argmax(probs_oof, axis=1)
        missed_sets[sk] = {sample_ids_ref[i] for i in vtdr_idx if preds_oof[i] <= 2}

    all_three_missed = sorted(set.intersection(*missed_sets.values()))
    any_missed = sorted(set.union(*missed_sets.values()))

    # Image quality diagnostics over APTOS val (n=700) + synthetic stress suite on E0 and E2 predictors
    val_quality_records: List[Dict[str, Any]] = []
    for idx, row in val_df_ref.iterrows():
        p = processed_dir / str(row["processed_relative_path"])
        with Image.open(p) as im:
            rgb_arr = np.asarray(im.convert("RGB"), dtype=np.uint8)
        qd = compute_retinal_quality_diagnostics(rgb_arr)
        val_quality_records.append(
            {
                "sample_id": sample_ids_ref[idx],
                "true_grade": int(row["standardized_grade_numeric"]),
                "phase8_accepted": qd["phase8_accepted"],
                "phase10_extended_accepted": qd["phase10_extended_accepted"],
                "laplacian_variance": qd["laplacian_variance"],
                "local_rms_contrast": qd["local_rms_contrast"],
                "saturated_fraction": qd.get("saturated_fraction", 0.0),
                "fov_border_touch_sides": qd["fov_border_touch_sides"],
            }
        )
    val_quality_df = pd.DataFrame(val_quality_records)
    val_quality_df.to_csv(output_dir / "aptos_val_quality_diagnostics_anonymized.csv", index=False)

    stress_suite: Dict[str, List[Dict[str, Any]]] = {}
    for sk in ("E0", "E2"):
        if sk in exp_bundles:
            pred_inst = DRBaselinePredictor(Path(experiments_root / exp_map[sk] / "best_checkpoint.pt"), device_preference=device_preference)
            stress_suite[sk] = run_synthetic_quality_stress_suite(pred_inst)

    # Plots
    rel_png = plot_reliability_comparison(exp_bundles, output_dir / "phase_10_calibration_reliability_diagrams.png")
    ci_png = plot_metrics_confidence_intervals(ci_by_exp, output_dir / "phase_10_per_class_confidence_intervals.png")
    triage_png = plot_uncertainty_triage_tradeoff(triage_by_exp, output_dir / "phase_10_uncertainty_triage_tradeoff.png")
    qual_png = plot_quality_diagnostics_distribution(
        val_quality_df, stress_suite.get("E2", []), output_dir / "phase_10_quality_diagnostics_distribution.png"
    )

    post_hashes = _snapshot_experiment_hashes(experiments_root, list(exp_map.values()))
    phase9_untouched = pre_hashes == post_hashes

    # Strip large numpy arrays from JSON serializable summary
    json_experiments: Dict[str, Any] = {}
    for sk, bundle in exp_bundles.items():
        cal_clean = {k: v for k, v in bundle["calibration"].items() if k not in ("raw_probs", "oof_calibrated_probs")}
        json_experiments[sk] = {
            **{k: v for k, v in bundle.items() if k != "calibration"},
            "calibration": cal_clean,
        }

    summary = {
        "phase": "Phase 10 - External Validation & Model Reliability",
        "scope_status": "Research reliability audit ONLY; NOT clinically validated or approved for diagnosis.",
        "split_manifest_sha256": manifest_sha,
        "phase9_artifacts_untouched_verified": phase9_untouched,
        "phase9_pre_hashes": pre_hashes,
        "phase9_post_hashes": post_hashes,
        "environment": collect_environment_metadata(),
        "external_dataset_readiness": external_readiness,
        "experiments": json_experiments,
        "cross_model_vtdr_miss_overlap": {
            "total_vtdr_samples": int(len(vtdr_idx)),
            "missed_by_all_three_count": len(all_three_missed),
            "missed_by_all_three_sample_ids": all_three_missed,
            "missed_by_at_least_one_count": len(any_missed),
            "per_model_vtdr_missed_counts": {k: len(v) for k, v in missed_sets.items()},
        },
        "aptos_val_image_quality_summary": {
            "total_samples": int(len(val_quality_df)),
            "phase8_accepted_count": int(val_quality_df["phase8_accepted"].sum()),
            "phase10_extended_accepted_count": int(val_quality_df["phase10_extended_accepted"].sum()),
            "phase10_extended_flagged_count": int((~val_quality_df["phase10_extended_accepted"]).sum()),
            "laplacian_variance_percentiles": {
                "p01": round(float(np.percentile(val_quality_df["laplacian_variance"], 1)), 4),
                "p05": round(float(np.percentile(val_quality_df["laplacian_variance"], 5)), 4),
                "p50": round(float(np.percentile(val_quality_df["laplacian_variance"], 50)), 4),
                "p95": round(float(np.percentile(val_quality_df["laplacian_variance"], 95)), 4),
            },
            "local_rms_contrast_percentiles": {
                "p01": round(float(np.percentile(val_quality_df["local_rms_contrast"], 1)), 4),
                "p05": round(float(np.percentile(val_quality_df["local_rms_contrast"], 5)), 4),
                "p50": round(float(np.percentile(val_quality_df["local_rms_contrast"], 50)), 4),
                "p95": round(float(np.percentile(val_quality_df["local_rms_contrast"], 95)), 4),
            },
        },
        "synthetic_quality_stress_suite": stress_suite,
        "plots_generated": [str(rel_png), str(ci_png), str(triage_png), str(qual_png)],
    }
    (output_dir / "phase_10_reliability_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary

