import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_pipeline.manifest import ManifestRecord
from data_pipeline.registry import VERIFIED_DATASET_REGISTRY


def generate_dataset_audit_report(
    dataset_name: str,
    records: List[ManifestRecord],
    reports_dir: Path,
    generate_charts: bool = True,
) -> Dict[str, Any]:
    """
    Produce a complete audit report (JSON, Markdown, and factual Matplotlib charts if rows exist)
    strictly from actual inspected manifest records. Never fabricates data.
    """
    reports_dir.mkdir(parents=True, exist_ok=True)
    registry_map = {r.dataset_key: r for r in VERIFIED_DATASET_REGISTRY}
    reg_meta = registry_map.get(dataset_name.lower())

    total_discovered = len(records)
    if total_discovered == 0:
        report_payload: Dict[str, Any] = {
            "dataset_name": dataset_name,
            "metadata": asdict(reg_meta) if reg_meta else None,
            "actual_inspection_executed": True,
            "files_present_on_disk": 0,
            "total_files_discovered": 0,
            "valid_images": 0,
            "invalid_images": 0,
            "duplicate_images": 0,
            "missing_images": 0,
            "missing_labels": 0,
            "label_distribution": {},
            "dimension_distribution": {},
            "format_distribution": {},
            "annotation_availability": reg_meta.annotation_format if reg_meta else "none",
            "patient_identifier_availability": reg_meta.patient_identifiers_available if reg_meta else False,
            "known_limitations": reg_meta.known_limitations_and_biases if reg_meta else "No local files present.",
            "recommended_future_use": reg_meta.suitable_roles if reg_meta else "Pending dataset acquisition.",
            "charts_generated": [],
        }
        json_path = reports_dir / f"{dataset_name}_audit_report.json"
        md_path = reports_dir / f"{dataset_name}_audit_report.md"
        with open(json_path, "w", encoding="utf-8") as jf:
            json.dump(report_payload, jf, indent=2)

        with open(md_path, "w", encoding="utf-8") as mf:
            mf.write(f"# Dataset Audit Report: {dataset_name}\n\n")
            mf.write("- **Local Files Discovered**: 0 (Dataset archive not yet present locally)\n")
            if reg_meta:
                mf.write(f"- **Official Source**: {reg_meta.official_source_url}\n")
                mf.write(f"- **License**: {reg_meta.license_and_terms}\n")
                mf.write(f"- **Access Gate**: {reg_meta.access_gate_details}\n")
                mf.write(f"- **Instructions**: {reg_meta.legitimate_acquisition_steps}\n")
        report_payload["json_path"] = str(json_path)
        report_payload["markdown_path"] = str(md_path)
        return report_payload

    df = pd.DataFrame([asdict(r) for r in records])
    valid_df = df[df["validation_status"] == "accepted"]
    invalid_df = df[df["validation_status"] == "rejected"]
    dup_df = df[df["validation_status"] == "duplicate_exact"]
    missing_df = df[df["validation_status"] == "missing_image"]
    missing_lbl_cnt = int((df["label_mapping_status"] == "missing").sum())

    label_dist = (
        valid_df["standardized_label"].fillna(valid_df["label_mapping_status"]).value_counts().to_dict()
        if not valid_df.empty
        else {}
    )
    format_dist = (
        valid_df["detected_media_type"].fillna("unknown").value_counts().to_dict()
        if not valid_df.empty
        else {}
    )

    if not valid_df.empty:
        widths = valid_df["width"].dropna().astype(int).to_numpy()
        heights = valid_df["height"].dropna().astype(int).to_numpy()
        dim_dist = {
            "width_min": int(np.min(widths)),
            "width_median": float(np.median(widths)),
            "width_max": int(np.max(widths)),
            "height_min": int(np.min(heights)),
            "height_median": float(np.median(heights)),
            "height_max": int(np.max(heights)),
            "unique_resolutions_count": int(valid_df.groupby(["width", "height"]).ngroups),
        }
    else:
        dim_dist = {}

    charts_generated: List[str] = []
    if generate_charts:
        # Chart 1: Accepted vs Rejected/Duplicate/Missing breakdown
        status_counts = df["validation_status"].value_counts()
        if not status_counts.empty:
            fig, ax = plt.subplots(figsize=(6, 4))
            status_counts.plot(kind="bar", ax=ax, color="#4a5320", edgecolor="#1c1d1a")
            ax.set_title(f"{dataset_name} — Validation Outcomes (n={total_discovered})")
            ax.set_ylabel("Image Count")
            ax.set_xlabel("Validation Status")
            plt.xticks(rotation=25, ha="right")
            plt.tight_layout()
            c1 = reports_dir / f"{dataset_name}_validation_breakdown.png"
            fig.savefig(c1, dpi=150)
            plt.close(fig)
            charts_generated.append(str(c1))

        # Chart 2: Standardized label class distribution (strictly from real valid rows)
        if label_dist:
            fig, ax = plt.subplots(figsize=(6, 4))
            pd.Series(label_dist).plot(kind="bar", ax=ax, color="#6f7d3e", edgecolor="#1c1d1a")
            ax.set_title(f"{dataset_name} — Inspected Label Distribution")
            ax.set_ylabel("Count")
            plt.xticks(rotation=25, ha="right")
            plt.tight_layout()
            c2 = reports_dir / f"{dataset_name}_label_distribution.png"
            fig.savefig(c2, dpi=150)
            plt.close(fig)
            charts_generated.append(str(c2))

        # Chart 3: Width vs Height scatter if >= 1 valid image
        if not valid_df.empty:
            fig, ax = plt.subplots(figsize=(6, 4))
            ax.scatter(valid_df["width"], valid_df["height"], alpha=0.7, color="#4a5320")
            ax.set_title(f"{dataset_name} — Image Dimension Distribution")
            ax.set_xlabel("Width (px)")
            ax.set_ylabel("Height (px)")
            plt.tight_layout()
            c3 = reports_dir / f"{dataset_name}_dimensions.png"
            fig.savefig(c3, dpi=150)
            plt.close(fig)
            charts_generated.append(str(c3))

    has_patient_ids = bool(
        not valid_df.empty and valid_df["patient_identifier"].notna().all() and (valid_df["patient_identifier"] != "").all()
    )

    report_payload = {
        "dataset_name": dataset_name,
        "metadata": asdict(reg_meta) if reg_meta else None,
        "actual_inspection_executed": True,
        "total_files_discovered": int(total_discovered),
        "valid_images": int(len(valid_df)),
        "invalid_images": int(len(invalid_df)),
        "duplicate_images": int(len(dup_df)),
        "missing_images": int(len(missing_df)),
        "missing_labels": missing_lbl_cnt,
        "label_distribution": {str(k): int(v) for k, v in label_dist.items()},
        "dimension_distribution": dim_dist,
        "format_distribution": {str(k): int(v) for k, v in format_dist.items()},
        "annotation_availability": list(df["annotation_availability"].unique()),
        "patient_identifier_availability": has_patient_ids,
        "known_limitations": (
            reg_meta.known_limitations_and_biases
            if reg_meta
            else "Audit reflects locally inspected files."
        ),
        "recommended_future_use": reg_meta.suitable_roles if reg_meta else "Research dataset evaluation.",
        "charts_generated": charts_generated,
    }

    json_path = reports_dir / f"{dataset_name}_audit_report.json"
    md_path = reports_dir / f"{dataset_name}_audit_report.md"
    with open(json_path, "w", encoding="utf-8") as jf:
        json.dump(report_payload, jf, indent=2)

    with open(md_path, "w", encoding="utf-8") as mf:
        mf.write(f"# Dataset Audit Report: {dataset_name}\n\n")
        mf.write(f"- **Total Files / Entries Inspected**: {report_payload['total_files_discovered']}\n")
        mf.write(f"- **Valid Accepted Images**: {report_payload['valid_images']}\n")
        mf.write(f"- **Invalid / Rejected**: {report_payload['invalid_images']}\n")
        mf.write(f"- **Exact SHA-256 Duplicates**: {report_payload['duplicate_images']}\n")
        mf.write(f"- **Missing Referenced Files**: {report_payload['missing_images']}\n")
        mf.write(f"- **Missing Labels**: {report_payload['missing_labels']}\n")
        mf.write(f"- **Patient Identifiers Present on All Valid Images**: {has_patient_ids}\n")
        mf.write(f"- **Label Distribution**: {json.dumps(report_payload['label_distribution'])}\n")
        mf.write(f"- **Format Distribution**: {json.dumps(report_payload['format_distribution'])}\n")
        mf.write(f"- **Dimensions Summary**: {json.dumps(report_payload['dimension_distribution'])}\n")

    report_payload["json_path"] = str(json_path)
    report_payload["markdown_path"] = str(md_path)
    return report_payload


def generate_phase8_pilot_comparison(
    sample_records: List[Dict[str, Any]],
    output_image_path: Path,
) -> Path:
    """
    Render side-by-side Before (Raw Original + Detected FOV BBox) vs After (Processed Aspect-Preserved)
    visual comparison grid for manual human/agent boundary inspection before full-dataset processing.
    """
    output_image_path.parent.mkdir(parents=True, exist_ok=True)
    n_rows = len(sample_records)
    fig, axes = plt.subplots(n_rows, 2, figsize=(10, 3.6 * n_rows))
    if n_rows == 1:
        axes = np.array([axes])

    import matplotlib.patches as patches

    for idx, item in enumerate(sample_records):
        ax_raw, ax_proc = axes[idx, 0], axes[idx, 1]
        raw_rgb = item["raw_rgb"]
        proc_rgb = item["proc_rgb"]
        x1, y1, x2, y2 = item["bbox"]

        ax_raw.imshow(raw_rgb)
        rect = patches.Rectangle(
            (x1, y1),
            max(1, x2 - x1),
            max(1, y2 - y1),
            linewidth=2,
            edgecolor="#00e5ff",
            facecolor="none",
        )
        ax_raw.add_patch(rect)
        ax_raw.set_title(
            f"RAW: {item['filename']} (Grade {item['grade']}, {item['orig_w']}x{item['orig_h']})\n"
            f"Crop BBox: ({x1},{y1})->({x2},{y2}) mean={item['mean_val']:.1f}",
            fontsize=8.5,
        )
        ax_raw.axis("off")

        ax_proc.imshow(proc_rgb)
        ax_proc.set_title(
            f"PROCESSED: {item['proc_w']}x{item['proc_h']} RGB ({item['interp']})\n"
            f"scale={item['scale']:.3f}, pad(L={item['pad_l']},T={item['pad_t']})",
            fontsize=8.5,
        )
        ax_proc.axis("off")

    plt.tight_layout()
    fig.savefig(output_image_path, dpi=150)
    plt.close(fig)
    return output_image_path


def generate_phase8_cleaning_charts(
    raw_class_counts: Dict[str, int],
    eligible_class_counts: Dict[str, int],
    split_counts_by_class: Dict[str, Dict[str, int]],
    original_dims: List[Tuple[int, int]],
    processed_dims: List[Tuple[int, int]],
    exclusion_counts: Dict[str, int],
    reports_dir: Path,
) -> Dict[str, str]:
    """Generate factual Phase 8 before/after class distribution, dimensions, and QC charts."""
    reports_dir.mkdir(parents=True, exist_ok=True)
    charts: Dict[str, str] = {}

    # 1. Class distribution before cleaning vs after cleaning vs train/val split
    classes = list(raw_class_counts.keys())
    raw_vals = [raw_class_counts.get(c, 0) for c in classes]
    elig_vals = [eligible_class_counts.get(c, 0) for c in classes]
    train_vals = [split_counts_by_class.get("train", {}).get(c, 0) for c in classes]
    val_vals = [split_counts_by_class.get("val", {}).get(c, 0) for c in classes]

    x = np.arange(len(classes))
    w = 0.2
    fig, ax = plt.subplots(figsize=(9, 4.8))
    ax.bar(x - 1.5 * w, raw_vals, w, label="Raw train.csv (n=3,662)", color="#9da685", edgecolor="#1c1d1a")
    ax.bar(x - 0.5 * w, elig_vals, w, label=f"Cleaned Eligible (n={sum(elig_vals)})", color="#4a5320", edgecolor="#1c1d1a")
    ax.bar(x + 0.5 * w, train_vals, w, label=f"Train Split (n={sum(train_vals)})", color="#6f7d3e", edgecolor="#1c1d1a")
    ax.bar(x + 1.5 * w, val_vals, w, label=f"Val Split (n={sum(val_vals)})", color="#b86b2b", edgecolor="#1c1d1a")
    ax.set_xticks(x)
    ax.set_xticklabels(classes, rotation=20, ha="right")
    ax.set_ylabel("Image Count")
    ax.set_title("APTOS 2019 Class Distribution — Raw vs Cleaned Eligible vs Train/Val Split")
    ax.legend()
    plt.tight_layout()
    c_cls = reports_dir / "phase_8_class_distribution_comparison.png"
    fig.savefig(c_cls, dpi=150)
    plt.close(fig)
    charts["class_distribution_chart"] = str(c_cls)

    # 2. Dimensions before (scatter) vs uniform processed 512x512 target
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    if original_dims:
        ow = [d[0] for d in original_dims]
        oh = [d[1] for d in original_dims]
        ax.scatter(ow, oh, alpha=0.55, label=f"Original Raw Dimensions (n={len(ow)})", color="#4a5320")
    if processed_dims:
        pw = [d[0] for d in processed_dims]
        ph = [d[1] for d in processed_dims]
        ax.scatter(pw, ph, marker="*", s=160, label=f"Processed Uniform Target (n={len(pw)})", color="#b86b2b", zorder=5)
    ax.set_xlabel("Width (px)")
    ax.set_ylabel("Height (px)")
    ax.set_title("APTOS Image Dimension Standardization (17 Raw Resolutions -> Uniform 512x512 RGB)")
    ax.legend()
    plt.tight_layout()
    c_dim = reports_dir / "phase_8_dimension_comparison.png"
    fig.savefig(c_dim, dpi=150)
    plt.close(fig)
    charts["dimension_chart"] = str(c_dim)

    # 3. Exclusion and Quality-Control Summary Chart
    fig, ax = plt.subplots(figsize=(8, 4.5))
    labels = list(exclusion_counts.keys())
    vals = list(exclusion_counts.values())
    colors = ["#4a5320" if "Eligible" in k else "#8c3b2b" for k in labels]
    ax.barh(labels, vals, color=colors, edgecolor="#1c1d1a")
    for idx, v in enumerate(vals):
        ax.text(v + max(vals) * 0.01, idx, str(v), va="center", fontsize=9)
    ax.set_xlabel("Image / Record Count")
    ax.set_title("APTOS 2019 Quality Control & Disposition Reconciliation")
    plt.tight_layout()
    c_qc = reports_dir / "phase_8_qc_summary_chart.png"
    fig.savefig(c_qc, dpi=150)
    plt.close(fig)
    charts["qc_summary_chart"] = str(c_qc)

    return charts
