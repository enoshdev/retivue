"""Multi-class diabetic retinopathy evaluation metrics, confusion matrix, QWK, OVR AUC, and safety slices."""

from typing import Any, Dict, List, Optional

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    cohen_kappa_score,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)

from ai.config import CLASS_INDEX_TO_LABEL


def compute_dr_evaluation_metrics(
    y_true: np.ndarray,
    y_probs: np.ndarray,
    class_map: Optional[Dict[int, str]] = None,
) -> Dict[str, Any]:
    """
    Compute comprehensive multi-class and screening-safety evaluation metrics from true integer labels
    (shape N,) and calibrated/softmax predicted class probabilities (shape N x 5).
    """
    cmap = class_map or CLASS_INDEX_TO_LABEL
    labels = sorted(cmap.keys())
    n_classes = len(labels)

    y_true_arr = np.asarray(y_true, dtype=np.int64)
    y_probs_arr = np.asarray(y_probs, dtype=np.float64)
    if y_true_arr.shape[0] == 0:
        raise ValueError("Cannot compute evaluation metrics on empty array.")
    if y_probs_arr.ndim != 2 or y_probs_arr.shape[1] != n_classes:
        raise ValueError(f"Expected y_probs shape (N, {n_classes}), got {y_probs_arr.shape}.")

    y_pred = np.argmax(y_probs_arr, axis=1)

    overall_acc = float(accuracy_score(y_true_arr, y_pred))
    macro_p, macro_r, macro_f1, _ = precision_recall_fscore_support(
        y_true_arr,
        y_pred,
        labels=labels,
        average="macro",
        zero_division=0,
    )
    weighted_f1 = float(
        precision_recall_fscore_support(
            y_true_arr,
            y_pred,
            labels=labels,
            average="weighted",
            zero_division=0,
        )[2]
    )

    per_p, per_r, per_f1, per_sup = precision_recall_fscore_support(
        y_true_arr,
        y_pred,
        labels=labels,
        average=None,
        zero_division=0,
    )

    cm = confusion_matrix(y_true_arr, y_pred, labels=labels)
    row_sums = cm.sum(axis=1, keepdims=True)
    cm_norm = np.divide(
        cm.astype(np.float64),
        row_sums,
        out=np.zeros_like(cm, dtype=np.float64),
        where=row_sums != 0,
    )

    # Quadratic Weighted Kappa requires >= 2 distinct labels or handles cleanly
    try:
        if len(np.unique(y_true_arr)) > 1 or len(np.unique(y_pred)) > 1:
            qwk = float(cohen_kappa_score(y_true_arr, y_pred, labels=labels, weights="quadratic"))
        else:
            qwk = 1.0 if np.array_equal(y_true_arr, y_pred) else 0.0
    except Exception:
        qwk = 0.0

    per_class: Dict[str, Dict[str, Any]] = {}
    roc_aucs: Dict[str, Optional[float]] = {}
    total_n = int(cm.sum())

    for idx, cls_id in enumerate(labels):
        name = cmap[cls_id]
        tp = int(cm[idx, idx])
        fn = int(cm[idx, :].sum() - tp)
        fp = int(cm[:, idx].sum() - tp)
        tn = int(total_n - tp - fn - fp)
        specificity = float(tn / (tn + fp)) if (tn + fp) > 0 else 0.0

        y_bin = (y_true_arr == cls_id).astype(np.int64)
        auc_val: Optional[float] = None
        if 0 < int(y_bin.sum()) < total_n:
            try:
                auc_val = round(float(roc_auc_score(y_bin, y_probs_arr[:, idx])), 6)
            except Exception:
                auc_val = None
        roc_aucs[name] = auc_val

        per_class[name] = {
            "grade": int(cls_id),
            "support": int(per_sup[idx]),
            "precision": round(float(per_p[idx]), 6),
            "recall_sensitivity": round(float(per_r[idx]), 6),
            "specificity": round(specificity, 6),
            "f1": round(float(per_f1[idx]), 6),
            "true_positives": tp,
            "false_negatives": fn,
            "false_positives": fp,
            "ovr_roc_auc": auc_val,
        }

    valid_aucs = [v for v in roc_aucs.values() if v is not None]
    macro_ovr_auc: Optional[float] = (
        round(float(np.mean(valid_aucs)), 6) if len(valid_aucs) == n_classes else None
    )

    # Medical Screening Safety Slices (Referable DR >= Grade 2; Vision-Threatening DR >= Grade 3)
    def _binary_slice(pos_grades: List[int]) -> Dict[str, Any]:
        true_pos_mask = np.isin(y_true_arr, pos_grades)
        pred_pos_mask = np.isin(y_pred, pos_grades)
        prob_pos = y_probs_arr[:, [labels.index(g) for g in pos_grades]].sum(axis=1)
        tp_c = int(np.sum(true_pos_mask & pred_pos_mask))
        fn_c = int(np.sum(true_pos_mask & ~pred_pos_mask))
        fp_c = int(np.sum(~true_pos_mask & pred_pos_mask))
        tn_c = int(np.sum(~true_pos_mask & ~pred_pos_mask))
        sens = float(tp_c / (tp_c + fn_c)) if (tp_c + fn_c) > 0 else 0.0
        spec = float(tn_c / (tn_c + fp_c)) if (tn_c + fp_c) > 0 else 0.0
        auc_b: Optional[float] = None
        if 0 < int(true_pos_mask.sum()) < total_n:
            try:
                auc_b = round(float(roc_auc_score(true_pos_mask.astype(int), prob_pos)), 6)
            except Exception:
                auc_b = None
        return {
            "support_positive": tp_c + fn_c,
            "true_positives": tp_c,
            "false_negatives": fn_c,
            "false_positives": fp_c,
            "sensitivity_recall": round(sens, 6),
            "specificity": round(spec, 6),
            "roc_auc": auc_b,
        }

    severe_slice = per_class.get(cmap.get(3, "SEVERE_NPDR"), {})
    pdr_slice = per_class.get(cmap.get(4, "PDR"), {})

    # Adjacent vs severe non-adjacent errors
    abs_err = np.abs(y_true_arr - y_pred)
    exact_match = int((abs_err == 0).sum())
    within_1_grade = int((abs_err <= 1).sum())
    off_by_2_or_more = int((abs_err >= 2).sum())

    return {
        "total_samples": total_n,
        "overall_accuracy": round(overall_acc, 6),
        "macro_precision": round(float(macro_p), 6),
        "macro_recall": round(float(macro_r), 6),
        "macro_f1": round(float(macro_f1), 6),
        "weighted_f1": round(weighted_f1, 6),
        "quadratic_weighted_kappa": round(qwk, 6),
        "macro_ovr_roc_auc": macro_ovr_auc,
        "severe_plus_pdr_mean_recall": round(
            float(
                (severe_slice.get("recall_sensitivity", 0.0) + pdr_slice.get("recall_sensitivity", 0.0))
                / 2.0
            ),
            6,
        ),
        "ordinal_error_breakdown": {
            "exact_grade_matches": exact_match,
            "within_1_adjacent_grade": within_1_grade,
            "within_1_grade_rate": round(within_1_grade / total_n, 6),
            "off_by_2_or_more_grades": off_by_2_or_more,
            "off_by_2_or_more_rate": round(off_by_2_or_more / total_n, 6),
        },
        "per_class": per_class,
        "clinical_safety_slices": {
            "referable_dr_grades_2_to_4": _binary_slice([2, 3, 4]),
            "vision_threatening_dr_grades_3_to_4": _binary_slice([3, 4]),
            "severe_npdr_grade_3": severe_slice,
            "pdr_grade_4": pdr_slice,
        },
        "confusion_matrix": cm.tolist(),
        "confusion_matrix_row_normalized": [[round(float(x), 4) for x in row] for row in cm_norm],
    }
