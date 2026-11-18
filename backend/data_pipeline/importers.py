from pathlib import Path
from typing import Dict, List, Optional
import pandas as pd

from data_pipeline.inspector import DatasetInputItem, SUPPORTED_EXTENSIONS_TO_FORMATS


def load_aptos_items(raw_dir: Path) -> List[DatasetInputItem]:
    """
    Parse official APTOS 2019 Blindness Detection directory structure:
    - raw/aptos/train.csv (`id_code`, `diagnosis`)
    - raw/aptos/train_images/<id_code>.png
    Also detects unreferenced files present in train_images/.
    """
    items: List[DatasetInputItem] = []
    train_csv = raw_dir / "train.csv"
    images_dir = raw_dir / "train_images"

    referenced_rel_paths = set()
    if train_csv.is_file():
        df = pd.read_csv(train_csv, dtype=str, keep_default_na=False)
        for _, row in df.iterrows():
            id_code = str(row.get("id_code", "")).strip()
            diagnosis = str(row.get("diagnosis", "")).strip()
            # Resolve actual image extension if non-png or fallback to .png
            candidate_rel = f"train_images/{id_code}.png"
            if images_dir.is_dir():
                matches = list(images_dir.glob(f"{id_code}.*"))
                if matches:
                    candidate_rel = f"train_images/{matches[0].name}"
            referenced_rel_paths.add(candidate_rel)
            items.append(
                DatasetInputItem(
                    relative_path=candidate_rel,
                    raw_label=diagnosis,
                    task_type="dr_grading",
                    patient_identifier=None,
                    patient_id_limitation_note="APTOS 2019 does not disclose patient IDs.",
                    annotation_availability="image_level_dr_grade_0_to_4",
                )
            )

    if images_dir.is_dir():
        for p in sorted(images_dir.iterdir()):
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS_TO_FORMATS:
                rel = f"train_images/{p.name}"
                if rel not in referenced_rel_paths:
                    items.append(
                        DatasetInputItem(
                            relative_path=rel,
                            raw_label=None,
                            task_type="dr_grading",
                            patient_identifier=None,
                            patient_id_limitation_note="APTOS 2019 does not disclose patient IDs.",
                            annotation_availability="unlabeled_image_file",
                        )
                    )

    # Catalog competition test.csv / test_images/ honestly without assuming test labels exist
    test_csv = raw_dir / "test.csv"
    test_images_dir = raw_dir / "test_images"
    referenced_test_paths = set()
    if test_csv.is_file():
        tdf = pd.read_csv(test_csv, dtype=str, keep_default_na=False)
        for _, row in tdf.iterrows():
            id_code = str(row.get("id_code", "")).strip()
            if not id_code:
                continue
            raw_diag = row.get("diagnosis")
            raw_lbl = str(raw_diag).strip() if raw_diag is not None and str(raw_diag).strip() != "" else None
            candidate_rel = f"test_images/{id_code}.png"
            if test_images_dir.is_dir():
                matches = list(test_images_dir.glob(f"{id_code}.*"))
                if matches:
                    candidate_rel = f"test_images/{matches[0].name}"
            referenced_test_paths.add(candidate_rel)
            items.append(
                DatasetInputItem(
                    relative_path=candidate_rel,
                    raw_label=raw_lbl,
                    task_type="dr_grading",
                    patient_identifier=None,
                    patient_id_limitation_note="APTOS 2019 does not disclose patient IDs.",
                    annotation_availability=(
                        "image_level_dr_grade_0_to_4"
                        if raw_lbl is not None
                        else "unlabeled_competition_test_set"
                    ),
                )
            )

    if test_images_dir.is_dir():
        for p in sorted(test_images_dir.iterdir()):
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS_TO_FORMATS:
                rel = f"test_images/{p.name}"
                if rel not in referenced_test_paths:
                    items.append(
                        DatasetInputItem(
                            relative_path=rel,
                            raw_label=None,
                            task_type="dr_grading",
                            patient_identifier=None,
                            patient_id_limitation_note="APTOS 2019 does not disclose patient IDs.",
                            annotation_availability="unlabeled_competition_test_set",
                        )
                    )
    return items


def load_idrid_items(raw_dir: Path) -> List[DatasetInputItem]:
    """
    Parse IDRiD Disease Grading CSV(s) and optional lesion segmentation masks cleanly,
    keeping pixel-level lesion masks strictly separate from DR grades.
    """
    items: List[DatasetInputItem] = []
    if not raw_dir.is_dir():
        return items

    # Index all candidate images once, preserving multiple matches when Training & Testing share stems
    img_candidates: Dict[str, List[Path]] = {}
    for p in sorted(raw_dir.rglob("*")):
        if p.is_file() and p.suffix.lower() in (".jpg", ".jpeg", ".png"):
            img_candidates.setdefault(p.stem, []).append(p)

    # Locate grading CSVs (commonly IDRiD_Disease Grading Training/Testing Labels.csv)
    csv_files = sorted(raw_dir.rglob("*.csv"))
    for csv_path in csv_files:
        df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
        cols_lower = {c.lower().strip(): c for c in df.columns}
        if "image name" not in cols_lower and "image_name" not in cols_lower:
            continue
        name_col = cols_lower.get("image name") or cols_lower.get("image_name")
        dr_col = cols_lower.get("retinopathy grade") or cols_lower.get("dr_grade")
        if not name_col or not dr_col:
            continue

        csv_name_lower = csv_path.name.lower()
        split_hint = (
            "testing"
            if ("testing" in csv_name_lower or "test" in csv_name_lower)
            else ("training" if ("training" in csv_name_lower or "train" in csv_name_lower) else None)
        )

        for _, row in df.iterrows():
            img_stem = str(row.get(name_col, "")).strip()
            if not img_stem:
                continue
            dr_grade = str(row.get(dr_col, "")).strip()
            cands = img_candidates.get(img_stem, [])
            matched_file: Optional[Path] = None
            if len(cands) == 1:
                matched_file = cands[0]
            elif len(cands) > 1 and split_hint is not None:
                hint_matches = [
                    c for c in cands if split_hint in c.relative_to(raw_dir).as_posix().lower()
                ]
                matched_file = hint_matches[0] if hint_matches else cands[0]
            elif cands:
                matched_file = cands[0]

            rel_path = (
                matched_file.relative_to(raw_dir).as_posix()
                if matched_file
                else f"images/{img_stem}.jpg"
            )
            items.append(
                DatasetInputItem(
                    relative_path=rel_path,
                    raw_label=dr_grade,
                    task_type="dr_grading",
                    patient_identifier=None,
                    patient_id_limitation_note="IDRiD de-identified IDs do not expose multi-visit patient links.",
                    annotation_availability="icdr_dr_grade_and_dme_risk",
                )
            )
    return items


def load_messidor2_items(raw_dir: Path) -> List[DatasetInputItem]:
    """
    Parse Messidor-2 pairing metadata and optional external adjudicated DR grades CSV
    (e.g. messidor2_dr_grades.csv) without inventing labels.
    """
    items: List[DatasetInputItem] = []
    if not raw_dir.is_dir():
        return items

    # Build external grades lookup if legally provided alongside raw archive
    grades_by_name: Dict[str, Dict[str, str]] = {}
    pairing_by_name: Dict[str, str] = {}

    for csv_path in sorted(raw_dir.rglob("*.csv")):
        df = pd.read_csv(csv_path, dtype=str, keep_default_na=False)
        cols = {c.lower().strip(): c for c in df.columns}
        if "image_id" in cols and "adjudicated_dr_grade" in cols:
            for _, row in df.iterrows():
                fname = str(row[cols["image_id"]]).strip()
                grades_by_name[fname] = {
                    "grade": str(row[cols["adjudicated_dr_grade"]]).strip(),
                    "gradable": str(row.get(cols.get("adjudicated_gradable", ""), "")).strip(),
                }
        elif "primary" in cols and "secondary" in cols:
            for idx, row in df.iterrows():
                exam_id = f"MESSIDOR2_EXAM_{idx:04d}"
                p1 = str(row[cols["primary"]]).strip()
                p2 = str(row[cols["secondary"]]).strip()
                if p1:
                    pairing_by_name[p1] = exam_id
                if p2:
                    pairing_by_name[p2] = exam_id

    for img_path in sorted(raw_dir.rglob("*")):
        if not img_path.is_file() or img_path.suffix.lower() not in SUPPORTED_EXTENSIONS_TO_FORMATS:
            continue
        rel_path = img_path.relative_to(raw_dir).as_posix()
        fname = img_path.name
        g_info = grades_by_name.get(fname) or grades_by_name.get(img_path.stem)
        exam_pid = pairing_by_name.get(fname)

        items.append(
            DatasetInputItem(
                relative_path=rel_path,
                raw_label=g_info["grade"] if g_info else None,
                gradable_flag=g_info["gradable"] if g_info else None,
                task_type="dr_grading",
                patient_identifier=exam_pid,
                patient_id_limitation_note=(
                    "Grouped by official Messidor-2 bilateral examination pair ID."
                    if exam_pid
                    else "Official pairing CSV not found alongside Messidor-2 images."
                ),
                annotation_availability=(
                    "external_adjudicated_dr_grade_joined"
                    if g_info
                    else "raw_images_only_no_dr_ground_truth"
                ),
            )
        )
    return items


def load_drive_items(raw_dir: Path) -> List[DatasetInputItem]:
    """
    Parse DRIVE vessel segmentation dataset keeping vessel masks strictly separate
    from DR severity classification tasks.
    """
    items: List[DatasetInputItem] = []
    if not raw_dir.is_dir():
        return items

    for subset in ("training", "test"):
        img_dir = raw_dir / subset / "images"
        if not img_dir.is_dir():
            continue
        manual_dir = raw_dir / subset / "1st_manual"
        for p in sorted(img_dir.iterdir()):
            if not p.is_file() or p.suffix.lower() not in SUPPORTED_EXTENSIONS_TO_FORMATS:
                continue
            rel = p.relative_to(raw_dir).as_posix()
            ann_paths: List[str] = []
            if manual_dir.is_dir():
                prefix = p.stem.split("_")[0]
                for m in sorted(manual_dir.glob(f"{prefix}_manual1.*")):
                    ann_paths.append(m.relative_to(raw_dir).as_posix())

            items.append(
                DatasetInputItem(
                    relative_path=rel,
                    raw_label=None,
                    task_type="vessel_segmentation",
                    patient_identifier=None,
                    patient_id_limitation_note="DRIVE does not expose patient identifiers.",
                    annotation_availability="binary_vessel_segmentation_mask",
                    annotation_relative_paths=ann_paths,
                )
            )
    return items


def load_generic_items(raw_dir: Path, labels_csv: Optional[Path] = None) -> List[DatasetInputItem]:
    """Load arbitrary folder + optional CSV mapping (`relative_path` or `filename`, `label`, optional `patient_id`)."""
    items: List[DatasetInputItem] = []
    if labels_csv and labels_csv.is_file():
        df = pd.read_csv(labels_csv, dtype=str, keep_default_na=False)
        for _, row in df.iterrows():
            rel = str(row.get("relative_path") or row.get("filename") or "").strip()
            lbl = row.get("label")
            pid = str(row.get("patient_id", "")).strip() or None
            ann_str = str(row.get("annotation_path", "")).strip()
            ann_list = [ann_str] if ann_str else []
            task = str(row.get("task_type") or "dr_grading").strip()
            items.append(
                DatasetInputItem(
                    relative_path=rel,
                    raw_label=lbl,
                    task_type=task,
                    patient_identifier=pid,
                    patient_id_limitation_note=(
                        "Patient identifier supplied by source metadata."
                        if pid
                        else "Patient identifiers not provided."
                    ),
                    annotation_relative_paths=ann_list,
                )
            )
        return items

    if raw_dir.is_dir():
        for p in sorted(raw_dir.rglob("*")):
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS_TO_FORMATS:
                items.append(
                    DatasetInputItem(
                        relative_path=p.relative_to(raw_dir).as_posix(),
                        raw_label=None,
                    )
                )
    return items
