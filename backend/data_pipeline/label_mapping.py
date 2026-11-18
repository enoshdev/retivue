from dataclasses import dataclass
from typing import Optional


DR_CANDIDATE_SCHEME = {
    0: "NO_DR",
    1: "MILD_NPDR",
    2: "MODERATE_NPDR",
    3: "SEVERE_NPDR",
    4: "PDR",
}


@dataclass(frozen=True)
class LabelMappingResult:
    raw_label: Optional[str]
    standardized_label: Optional[str]
    standardized_grade_numeric: Optional[int]
    mapping_status: str  # 'mapped', 'unresolved', 'missing', 'non_dr_task'
    mapping_rationale: str


def _parse_int_0_to_4(raw_val: Optional[str]) -> Optional[int]:
    if raw_val is None:
        return None
    cleaned = str(raw_val).strip()
    if not cleaned:
        return None
    # Strictly match integer digits '0'..'4' (reject floats like '2.5', negative '-1', or text unless explicitly handled)
    if cleaned in ("0", "1", "2", "3", "4"):
        return int(cleaned)
    return None


def map_dr_label(
    dataset_name: str,
    raw_label: Optional[str],
    task_type: str = "dr_grading",
    gradable_flag: Optional[str] = None,
) -> LabelMappingResult:
    """
    Map dataset-specific labels strictly onto the documented 5-class ICDR/APTOS scheme
    without forcing incompatible tasks or hiding ambiguous entries.
    """
    ds = (dataset_name or "").strip().lower()
    raw_str = None if raw_label is None else str(raw_label).strip()

    # Keep DRIVE vessel extraction masks strictly distinct from DR severity classification
    if ds == "drive" or task_type == "vessel_segmentation":
        return LabelMappingResult(
            raw_label=raw_str,
            standardized_label=None,
            standardized_grade_numeric=None,
            mapping_status="non_dr_task",
            mapping_rationale=(
                "DRIVE binary vessel segmentation dataset must remain separate from DR severity labels."
            ),
        )

    # Keep pixel-level lesion segmentation annotations strictly distinct from image-level DR grades
    if task_type == "lesion_segmentation":
        return LabelMappingResult(
            raw_label=raw_str,
            standardized_label=None,
            standardized_grade_numeric=None,
            mapping_status="non_dr_task",
            mapping_rationale=(
                "IDRiD pixel-level lesion segmentation mask kept separate from image-level DR severity grades."
            ),
        )

    # Missing raw label
    if raw_str is None or raw_str == "" or raw_str.lower() in ("nan", "null", "none"):
        return LabelMappingResult(
            raw_label=raw_str,
            standardized_label=None,
            standardized_grade_numeric=None,
            mapping_status="missing",
            mapping_rationale="No DR severity label provided for this record.",
        )

    # Handle Messidor-2 external adjudicated grades + gradability gate cleanly
    if ds == "messidor2":
        if gradable_flag is not None and str(gradable_flag).strip() in ("0", "false", "False", "no", "ungradable"):
            return LabelMappingResult(
                raw_label=raw_str,
                standardized_label=None,
                standardized_grade_numeric=None,
                mapping_status="unresolved",
                mapping_rationale=(
                    "Messidor-2 adjudicated_gradable indicates ungradable image; cannot safely map to DR grade."
                ),
            )
        parsed = _parse_int_0_to_4(raw_str)
        if parsed is not None:
            return LabelMappingResult(
                raw_label=raw_str,
                standardized_label=DR_CANDIDATE_SCHEME[parsed],
                standardized_grade_numeric=parsed,
                mapping_status="mapped",
                mapping_rationale="Mapped external adjudicated Messidor-2 ICDR 0..4 grade.",
            )
        return LabelMappingResult(
            raw_label=raw_str,
            standardized_label=None,
            standardized_grade_numeric=None,
            mapping_status="unresolved",
            mapping_rationale=f"Unrecognized or ambiguous Messidor-2 label '{raw_str}'; marked unresolved.",
        )

    # APTOS 2019 & IDRiD ICDR 0..4 image-level grading
    if ds in ("aptos", "idrid", "synthetic_test", "generic"):
        parsed = _parse_int_0_to_4(raw_str)
        if parsed is not None:
            return LabelMappingResult(
                raw_label=raw_str,
                standardized_label=DR_CANDIDATE_SCHEME[parsed],
                standardized_grade_numeric=parsed,
                mapping_status="mapped",
                mapping_rationale=f"Mapped {ds.upper()} 0..4 DR severity scale cleanly to ICDR scheme.",
            )
        return LabelMappingResult(
            raw_label=raw_str,
            standardized_label=None,
            standardized_grade_numeric=None,
            mapping_status="unresolved",
            mapping_rationale=f"Ambiguous or out-of-range label '{raw_str}' for {ds}; marked unresolved.",
        )

    return LabelMappingResult(
        raw_label=raw_str,
        standardized_label=None,
        standardized_grade_numeric=None,
        mapping_status="unresolved",
        mapping_rationale=f"Dataset '{ds}' has no verified DR severity mapping rule.",
    )
