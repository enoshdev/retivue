import csv
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional


@dataclass
class ManifestRecord:
    dataset_name: str
    original_filename: str
    relative_path: str
    file_extension: str
    detected_media_type: Optional[str]
    file_size_bytes: Optional[int]
    width: Optional[int]
    height: Optional[int]
    channels: Optional[int]
    sha256_checksum: Optional[str]
    perceptual_hash: Optional[str]
    raw_label: Optional[str]
    standardized_label: Optional[str]
    standardized_grade_numeric: Optional[int]
    label_mapping_status: str
    label_mapping_rationale: str
    annotation_availability: str
    patient_identifier: Optional[str]
    patient_id_limitation_note: str
    import_timestamp: str
    validation_status: str  # 'accepted', 'rejected', 'duplicate_exact', 'missing_image'
    rejection_reason: Optional[str]
    is_near_duplicate_candidate: bool = False
    near_duplicate_of: Optional[str] = None


MANIFEST_FIELDNAMES = list(ManifestRecord.__dataclass_fields__.keys())


def sort_manifest_records(records: List[ManifestRecord]) -> List[ManifestRecord]:
    """Deterministic ordering guarantees reproducible manifests across runs."""
    return sorted(
        records,
        key=lambda r: (
            r.dataset_name or "",
            r.relative_path or "",
            r.original_filename or "",
        ),
    )


def write_manifest_csv(records: List[ManifestRecord], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sort_manifest_records(records)
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDNAMES)
        writer.writeheader()
        for rec in ordered:
            writer.writerow(asdict(rec))
    return output_path


def write_manifest_jsonl(records: List[ManifestRecord], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sort_manifest_records(records)
    with open(output_path, "w", encoding="utf-8") as f:
        for rec in ordered:
            f.write(json.dumps(asdict(rec), ensure_ascii=False) + "\n")
    return output_path


def read_manifest_jsonl(input_path: Path) -> List[ManifestRecord]:
    records: List[ManifestRecord] = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            data = json.loads(line)
            records.append(ManifestRecord(**data))
    return records
