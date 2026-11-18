"""Model evaluation runner generating calibrated predictions, confusion matrix, ROC curves, and clinical reports."""

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import roc_curve
from torch.utils.data import DataLoader

from ai.checkpoint import verify_and_load_checkpoint
from ai.config import CLASS_INDEX_TO_LABEL, resolve_torch_device
from ai.dataset import RetinalSplitDataset, load_phase8_split_dataframe
from ai.metrics import compute_dr_evaluation_metrics
from ai.models import build_classifier_model
from ai.transforms import build_retinal_transforms
from data_pipeline.directory_manager import DatasetDirectoryManager


def _plot_confusion_matrix(cm: List[List[int]], class_names: List[str], out_path: Path, title: str) -> None:
    arr = np.asarray(cm, dtype=np.int64)
    row_sum = arr.sum(axis=1, keepdims=True)
    norm = np.divide(arr.astype(float), row_sum, out=np.zeros_like(arr, dtype=float), where=row_sum != 0)

    fig, ax = plt.subplots(figsize=(7.5, 6.2))
    im = ax.imshow(norm, interpolation="nearest", cmap="YlGn", vmin=0.0, vmax=1.0)
    ax.figure.colorbar(im, ax=ax, fraction=0.046, pad=0.04, label="Row-Normalized Recall")
    ax.set(
        xticks=np.arange(len(class_names)),
        yticks=np.arange(len(class_names)),
        xticklabels=class_names,
        yticklabels=class_names,
        ylabel="True DR Grade",
        xlabel="Predicted DR Grade",
        title=title,
    )
    plt.setp(ax.get_xticklabels(), rotation=25, ha="right")

    for i in range(arr.shape[0]):
        for j in range(arr.shape[1]):
            pct = norm[i, j] * 100.0
            txt_color = "white" if norm[i, j] > 0.55 else "#1c1d1a"
            ax.text(j, i, f"{arr[i, j]}\n({pct:.1f}%)", ha="center", va="center", color=txt_color, fontsize=8.5)

    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _plot_ovr_roc_curves(
    y_true: np.ndarray,
    y_probs: np.ndarray,
    class_map: Dict[int, str],
    per_class_metrics: Dict[str, Any],
    out_path: Path,
) -> Optional[str]:
    fig, ax = plt.subplots(figsize=(7.5, 5.8))
    plotted = 0
    colors = ["#4a5320", "#6f7d3e", "#d4a024", "#c95b1e", "#8c2323"]

    for idx, cls_id in enumerate(sorted(class_map.keys())):
        name = class_map[cls_id]
        y_bin = (y_true == cls_id).astype(int)
        if y_bin.sum() == 0 or y_bin.sum() == len(y_bin):
            continue
        fpr, tpr, _ = roc_curve(y_bin, y_probs[:, idx])
        auc_val = per_class_metrics.get(name, {}).get("ovr_roc_auc")
        lbl = f"{cls_id}: {name} (AUC={auc_val:.3f})" if auc_val is not None else f"{cls_id}: {name}"
        ax.plot(fpr, tpr, lw=1.8, color=colors[idx % len(colors)], label=lbl)
        plotted += 1

    if plotted == 0:
        plt.close(fig)
        return None

    ax.plot([0, 1], [0, 1], linestyle="--", color="#888888", lw=1.0, label="Chance (AUC=0.500)")
    ax.set_xlabel("False Positive Rate (1 - Specificity)")
    ax.set_ylabel("True Positive Rate (Sensitivity)")
    ax.set_title("APTOS Validation One-vs-Rest ROC Curves")
    ax.legend(loc="lower right", fontsize=8.5)
    plt.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return str(out_path)


def evaluate_checkpoint_on_split(
    checkpoint_path: Path,
    split_manifest_csv: Path,
    processed_dataset_dir: Path,
    output_dir: Path,
    split_name: str = "val",
    batch_size: int = 16,
    num_workers: int = 0,
    device_preference: str = "auto",
) -> Dict[str, Any]:
    """Run deterministic evaluation of a saved checkpoint on a non-training split (strictly 'val')."""
    if split_name != "val":
        raise ValueError("Evaluation is strictly bounded to 'val' in Phase 9 (never evaluate on official test_images).")

    dev_info = resolve_torch_device(device_preference)
    device = torch.device(dev_info["device"])

    ckpt = verify_and_load_checkpoint(checkpoint_path, map_location="cpu")
    arch = str(ckpt.get("architecture", "efficientnet_b0"))
    num_classes = int(ckpt.get("num_classes", 5))
    input_size = int(ckpt.get("input_size", 512))
    dropout_p = float(ckpt.get("dropout_p", 0.3))
    norm_mean = tuple(float(x) for x in ckpt.get("norm_mean", (0.485, 0.456, 0.406)))
    norm_std = tuple(float(x) for x in ckpt.get("norm_std", (0.229, 0.224, 0.225)))
    raw_cmap = ckpt.get("class_mapping", CLASS_INDEX_TO_LABEL)
    class_map: Dict[int, str] = {int(k): str(v) for k, v in raw_cmap.items()}

    df, manifest_sha = load_phase8_split_dataframe(
        split_manifest_csv=split_manifest_csv,
        processed_dataset_dir=processed_dataset_dir,
        split_filter=split_name,
        verify_files_exist=True,
    )
    eval_tf = build_retinal_transforms(
        input_size=input_size,
        mean=norm_mean,  # type: ignore[arg-type]
        std=norm_std,  # type: ignore[arg-type]
        is_train=False,
        augmentation_enabled=False,
    )
    ds = RetinalSplitDataset(df, processed_dataset_dir, transform=eval_tf)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False, num_workers=num_workers)

    mem_fmt = torch.channels_last if device.type == "cpu" else torch.contiguous_format
    model = build_classifier_model(
        architecture=arch,
        num_classes=num_classes,
        pretrained=False,
        dropout_p=dropout_p,
    )
    model.load_state_dict(ckpt["model_state_dict"])
    model.to(device, memory_format=mem_fmt)
    model.eval()

    all_probs: List[np.ndarray] = []
    all_labels: List[np.ndarray] = []
    all_indices: List[np.ndarray] = []

    with torch.inference_mode():
        for x_batch, y_batch, idx_batch in loader:
            x_batch = x_batch.to(device, memory_format=mem_fmt)
            logits = model(x_batch)
            probs = torch.softmax(logits, dim=1).detach().cpu().numpy()
            all_probs.append(probs)
            all_labels.append(y_batch.numpy())
            all_indices.append(idx_batch.numpy())

    y_probs = np.concatenate(all_probs, axis=0)
    y_true = np.concatenate(all_labels, axis=0)
    indices = np.concatenate(all_indices, axis=0)

    metrics = compute_dr_evaluation_metrics(y_true=y_true, y_probs=y_probs, class_map=class_map)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save exact per-sample predictions CSV
    pred_csv = output_dir / f"{split_name}_predictions.csv"
    y_pred = np.argmax(y_probs, axis=1)
    class_keys = sorted(class_map.keys())
    with open(pred_csv, "w", newline="", encoding="utf-8") as pf:
        fields = [
            "relative_path",
            "sha256_checksum",
            "overlaps_official_test_sha256",
            "true_grade",
            "true_label",
            "pred_grade",
            "pred_label",
            "pred_confidence",
            "is_correct",
            "abs_grade_error",
        ] + [f"prob_{k}_{class_map[k]}" for k in class_keys]
        w = csv.DictWriter(pf, fieldnames=fields)
        w.writeheader()
        for pos, row_idx in enumerate(indices):
            src_row = df.iloc[int(row_idx)]
            tg = int(y_true[pos])
            pg = int(y_pred[pos])
            rec = {
                "relative_path": src_row["relative_path"],
                "sha256_checksum": src_row["sha256_checksum"],
                "overlaps_official_test_sha256": bool(src_row.get("overlaps_official_test_sha256", False)),
                "true_grade": tg,
                "true_label": class_map[tg],
                "pred_grade": pg,
                "pred_label": class_map[pg],
                "pred_confidence": round(float(y_probs[pos, pg]), 6),
                "is_correct": tg == pg,
                "abs_grade_error": abs(tg - pg),
            }
            for k_idx, k in enumerate(class_keys):
                rec[f"prob_{k}_{class_map[k]}"] = round(float(y_probs[pos, k_idx]), 6)
            w.writerow(rec)

    class_names = [f"{k}:{class_map[k]}" for k in class_keys]
    cm_path = output_dir / f"{split_name}_confusion_matrix.png"
    _plot_confusion_matrix(
        metrics["confusion_matrix"],
        class_names=class_names,
        out_path=cm_path,
        title=f"{arch} ({split_name}, n={len(y_true)}) — QWK={metrics['quadratic_weighted_kappa']:.3f}, MacroF1={metrics['macro_f1']:.3f}",
    )
    roc_path = _plot_ovr_roc_curves(
        y_true=y_true,
        y_probs=y_probs,
        class_map=class_map,
        per_class_metrics=metrics["per_class"],
        out_path=output_dir / f"{split_name}_roc_curves.png",
    )

    limitation_disclaimer = (
        "APTOS 2019 lacks public patient identifiers; therefore patient-level split independence "
        "cannot be guaranteed. Validation performance reflects single-dataset research baseline only "
        "and must NOT be interpreted as prospective clinical diagnostic accuracy."
    )

    report = {
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "split": split_name,
        "architecture": arch,
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": ckpt["_verified_sha256"],
        "checkpoint_epoch": int(ckpt.get("epoch", -1)),
        "split_manifest_sha256": manifest_sha,
        "device_used": dev_info,
        "patient_level_split_verified": False,
        "limitation_disclaimer": limitation_disclaimer,
        "metrics": metrics,
        "artifacts": {
            "predictions_csv": str(pred_csv),
            "confusion_matrix_png": str(cm_path),
            "roc_curves_png": roc_path,
        },
    }

    json_path = output_dir / "evaluation_report.json"
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(report, jf, indent=2)

    md_path = output_dir / "evaluation_report.md"
    with open(md_path, "w", encoding="utf-8") as mf:
        mf.write(f"# RETIVUE Evaluation Report — {arch} (`{split_name}`, n={len(y_true)})\n\n")
        mf.write(f"> [!WARNING]\n> {limitation_disclaimer}\n\n")
        mf.write(f"- **Checkpoint SHA-256**: `{ckpt['_verified_sha256']}` (epoch {report['checkpoint_epoch']})\n")
        mf.write(f"- **Split Manifest SHA-256**: `{manifest_sha}`\n")
        mf.write(f"- **Overall Accuracy**: `{metrics['overall_accuracy']:.4f}` *(secondary — skewed by 51.29% NO_DR prevalence)*\n")
        mf.write(f"- **Macro F1**: `{metrics['macro_f1']:.4f}` | **Macro Recall**: `{metrics['macro_recall']:.4f}` | **Macro Precision**: `{metrics['macro_precision']:.4f}`\n")
        mf.write(f"- **Quadratic Weighted Kappa (QWK)**: `{metrics['quadratic_weighted_kappa']:.4f}`\n")
        mf.write(f"- **Macro OVR ROC-AUC**: `{metrics['macro_ovr_roc_auc']}`\n\n")
        mf.write("## Per-Class Metrics\n\n| Class | Support | Precision | Recall | Specificity | F1 | FN | OVR AUC |\n| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n")
        for cname, cstats in metrics["per_class"].items():
            mf.write(
                f"| `{cstats['grade']}: {cname}` | {cstats['support']} | {cstats['precision']:.4f} | "
                f"{cstats['recall_sensitivity']:.4f} | {cstats['specificity']:.4f} | {cstats['f1']:.4f} | "
                f"{cstats['false_negatives']} | {cstats['ovr_roc_auc']} |\n"
            )
        ref = metrics["clinical_safety_slices"]["referable_dr_grades_2_to_4"]
        vtdr = metrics["clinical_safety_slices"]["vision_threatening_dr_grades_3_to_4"]
        mf.write("\n## Screening Safety Slices\n\n")
        mf.write(f"- **Referable DR (Grades 2–4, n={ref['support_positive']})**: Sensitivity={ref['sensitivity_recall']:.4f}, Specificity={ref['specificity']:.4f}, FN={ref['false_negatives']}, AUC={ref['roc_auc']}\n")
        mf.write(f"- **Vision-Threatening DR (Grades 3–4, n={vtdr['support_positive']})**: Sensitivity={vtdr['sensitivity_recall']:.4f}, Specificity={vtdr['specificity']:.4f}, FN={vtdr['false_negatives']}, AUC={vtdr['roc_auc']}\n")

    report["artifacts"]["evaluation_report_json"] = str(json_path)
    report["artifacts"]["evaluation_report_md"] = str(md_path)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a RETIVUE Phase 9 checkpoint on validation split.")
    parser.add_argument("--checkpoint", required=True, help="Path to best_checkpoint.pt")
    parser.add_argument("--output-dir", required=True, help="Directory for evaluation outputs")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    dirs = DatasetDirectoryManager().ensure_structure()
    res = evaluate_checkpoint_on_split(
        checkpoint_path=Path(args.checkpoint),
        split_manifest_csv=dirs.reports / "phase_8_split_manifest.csv",
        processed_dataset_dir=dirs.processed / "aptos",
        output_dir=Path(args.output_dir),
        split_name="val",
        batch_size=args.batch_size,
        device_preference=args.device,
    )
    print(json.dumps({"metrics": res["metrics"], "artifacts": res["artifacts"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
