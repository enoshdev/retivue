import csv
import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class DatasetMetadataRecord:
    dataset_key: str
    display_name: str
    official_source_url: str
    publisher_or_owner: str
    license_and_terms: str
    commercial_use_status: str  # 'restricted_or_requires_clearance', 'allowed_with_attribution', 'prohibited', 'unclear_noncommercial'
    registration_or_application_required: bool
    access_gate_details: str
    verified_total_image_count: str
    label_categories: str
    annotation_format: str
    image_formats: str
    image_dimensions: str
    camera_and_acquisition_specs: str
    patient_identifiers_available: bool
    patient_level_separation_possible: bool
    known_limitations_and_biases: str
    suitable_roles: str
    phase5_acquisition_status: str  # 'downloaded', 'investigated_access_pending'
    legitimate_acquisition_steps: str


VERIFIED_DATASET_REGISTRY: List[DatasetMetadataRecord] = [
    DatasetMetadataRecord(
        dataset_key="aptos",
        display_name="APTOS 2019 Blindness Detection",
        official_source_url="https://www.kaggle.com/competitions/aptos2019-blindness-detection",
        publisher_or_owner="Asia Pacific Tele-Ophthalmology Society (APTOS) & Aravind Eye Hospital, India",
        license_and_terms="Kaggle Competition Rules (research, educational, and competition benchmarking; winning code requires OSI open-source license, dataset governed by competition terms).",
        commercial_use_status="restricted_or_requires_clearance",
        registration_or_application_required=True,
        access_gate_details="Requires Kaggle user account, acceptance of APTOS 2019 Competition Rules, and Kaggle API token (~/.kaggle/kaggle.json).",
        verified_total_image_count="3,662 labeled training images (0: 1,805; 1: 370; 2: 999; 3: 193; 4: 295); ~13,000 hidden competition test images unavailable locally (~1,928 public sample test images without ground-truth labels).",
        label_categories="5-class DR severity scale (0: No DR, 1: Mild, 2: Moderate, 3: Severe, 4: Proliferative DR)",
        annotation_format="CSV (train.csv mapping id_code -> integer diagnosis 0..4)",
        image_formats="PNG (.png)",
        image_dimensions="Variable multi-clinic dimensions ranging from ~250px/square crops (~1000x1000) up to 3216x2136 px",
        camera_and_acquisition_specs="Multi-vendor cameras across rural Indian screening camps and Aravind Eye Hospital clinics; specific per-image camera metadata stripped.",
        patient_identifiers_available=False,
        patient_level_separation_possible=False,
        known_limitations_and_biases=(
            "Severe class imbalance (1,805 No DR vs 193 Severe NPDR). Significant noise, lighting/focus artifacts, and circular border variations across outreach camps. "
            "Lacks public patient identifiers (reported ~193 patients/sessions in literature, unmapped in CSV), preventing verifiable patient-level train/val splitting."
        ),
        suitable_roles="Primary candidate for 5-class DR severity model development (with strict awareness of missing patient-level split guarantees).",
        phase5_acquisition_status="investigated_access_pending",
        legitimate_acquisition_steps=(
            "1. Sign in to Kaggle and accept rules at https://www.kaggle.com/competitions/aptos2019-blindness-detection/rules. "
            "2. Generate API token (kaggle.json) under Account Settings -> API. "
            "3. Run `kaggle competitions download -c aptos2019-blindness-detection` and extract into DATASET_ROOT/raw/aptos/."
        ),
    ),
    DatasetMetadataRecord(
        dataset_key="idrid",
        display_name="IDRiD (Indian Diabetic Retinopathy Image Dataset)",
        official_source_url="https://idrid.grand-challenge.org/ (Official DataPort: https://ieee-dataport.org/open-access/indian-diabetic-retinopathy-image-dataset-idrid)",
        publisher_or_owner="Shri Guru Gobind Singhji Institute of Engineering and Technology & Eye Clinic (Sushrusha Hospital), Nanded, Maharashtra, India (Porwal et al.)",
        license_and_terms="Creative Commons Attribution 4.0 International (CC-BY 4.0).",
        commercial_use_status="allowed_with_attribution",
        registration_or_application_required=True,
        access_gate_details="Requires free IEEE DataPort or Grand Challenge account sign-in to access download archives (Segmentation.zip, Disease Grading.zip, Localization.zip).",
        verified_total_image_count="516 total color fundus images in Disease Grading (413 train / 103 test); 81 images in pixel-level Lesion Segmentation subset (54 train / 27 test).",
        label_categories="Disease Grading: ICDR DR grade (0..4) + DME risk (0..2). Segmentation: binary masks for Microaneurysms (MA), Hemorrhages (HE), Hard Exudates (EX), Soft Exudates (SE), Optic Disc (OD). Localization: OD & Fovea (x,y) coordinates.",
        annotation_format="CSV files for DR/DME grading & OD/Fovea coordinates; binary TIFF (.tif) pixel masks for lesions and optic disc.",
        image_formats="JPEG (.jpg) originals; TIFF (.tif) ground-truth segmentation masks.",
        image_dimensions="4288 x 2848 pixels (standard native capture resolution, ~800 KB per JPG).",
        camera_and_acquisition_specs="Kowa VX-10 alpha digital fundus camera, 50-degree field of view (FOV), macula-centered.",
        patient_identifiers_available=False,
        patient_level_separation_possible=False,
        known_limitations_and_biases=(
            "Small total sample size (516 graded; only 81 segmentation masks) and single-clinic / single-camera capture (Kowa VX-10 alpha in Nanded, India). "
            "De-identified image names do not expose explicit patient/visit grouping across multiple images if present."
        ),
        suitable_roles="Indian population DR severity fine-tuning/validation AND separate pixel-level lesion segmentation / explainability evaluation (keep lesion masks strictly distinct from DR grade labels).",
        phase5_acquisition_status="investigated_access_pending",
        legitimate_acquisition_steps=(
            "1. Register/sign in at https://ieee-dataport.org/open-access/indian-diabetic-retinopathy-image-dataset-idrid or https://idrid.grand-challenge.org/. "
            "2. Download Disease Grading, Segmentation, and Localization archives under CC-BY 4.0. "
            "3. Extract into DATASET_ROOT/raw/idrid/."
        ),
    ),
    DatasetMetadataRecord(
        dataset_key="messidor2",
        display_name="Messidor-2 (with separate adjudicated DR reference grades)",
        official_source_url="https://www.adcis.net/en/third-party/messidor2/",
        publisher_or_owner="ADCIS & LaTIM Laboratory / Brest University Hospital (images); independent adjudicated DR/DME/gradability grades published by Google Brain/AI team (Krause et al. 2018)",
        license_and_terms="ADCIS Research & Educational License: free strictly for non-commercial research and education; copying, redistribution, and commercial use explicitly prohibited.",
        commercial_use_status="prohibited",
        registration_or_application_required=True,
        access_gate_details="Requires submitting an online access application form on adcis.net to receive a time-limited (7-day) personal download link. Official package contains images & pairing only; DR clinical grades must be obtained separately (e.g., CC0 Google adjudicated Messidor-2 DR Grades CSV).",
        verified_total_image_count="1,748 macula-centered fundus images spanning 874 patient examinations (1,058 PNG from Messidor-Original + 690 JPG from Messidor-Extension).",
        label_categories="Raw ADCIS release: image-to-examination pairing only (no DR ground truth). Separate Google/Krause et al. adjudicated labels: DR grade (0..4 ICDR), DME (0/1), and Gradability (0/1).",
        annotation_format="Official pairing spreadsheet (CSV/XLS); third-party adjudicated DR grades CSV mapping image filename -> adjudicated_dr_grade, adjudicated_dme, adjudicated_gradable.",
        image_formats="Mixed PNG (.png for Messidor-Original 529 exams) and JPEG (.jpg for Messidor-Extension 345 exams).",
        image_dimensions="Discrete resolutions: 1440x960, 2240x1488, and 2304x1536 pixels (8-bit per color plane).",
        camera_and_acquisition_specs="Topcon TRC NW6 non-mydriatic 3CCD fundus camera, 45-degree FOV, macula-centered.",
        patient_identifiers_available=True,
        patient_level_separation_possible=True,
        known_limitations_and_biases=(
            "Strictly non-commercial license prohibits commercial model training/redistribution. Mixed image formats (PNG + JPG) and 3 distinct resolutions. "
            "Population is European/French hospital cohort rather than Indian screening camps, so external testing checks cross-population generalization. "
            "Pairings link OD/OS eyes within the same patient examination (874 exam groups)."
        ),
        suitable_roles="External held-out evaluation benchmark for DR severity & gradability ONLY (never mix into training splits; observe non-commercial license constraints).",
        phase5_acquisition_status="investigated_access_pending",
        legitimate_acquisition_steps=(
            "1. Submit online request form at https://www.adcis.net/en/third-party/messidor2/ for research/education access. "
            "2. Download archive via emailed personal 7-day link and extract to DATASET_ROOT/raw/messidor2/. "
            "3. Obtain adjudicated DR grades CSV (e.g., Krause et al. / Kaggle MESSIDOR-2 DR Grades CC0) to join labels without modifying raw images."
        ),
    ),
    DatasetMetadataRecord(
        dataset_key="drive",
        display_name="DRIVE (Digital Retinal Images for Vessel Extraction)",
        official_source_url="https://drive.grand-challenge.org/",
        publisher_or_owner="Image Sciences Institute, University Medical Center Utrecht (UMC Utrecht), Netherlands (Staal et al., 2004)",
        license_and_terms="Academic research, educational, and comparative benchmarking license via Grand Challenge with mandatory citation (Staal et al., IEEE TMI 2004). Commercial rights unclear / not permissively granted.",
        commercial_use_status="unclear_noncommercial",
        registration_or_application_required=True,
        access_gate_details="Requires registered user sign-in on grand-challenge.org to download the training and test archives.",
        verified_total_image_count="40 color fundus images total (20 training + 20 testing), of which 33 show no signs of DR and 7 show signs of mild early DR/background abnormalities.",
        label_categories="Binary retinal blood vessel segmentation masks (1st_manual for all; 2nd_manual observer on test set) + binary FOV masks. NOT a 5-class DR severity dataset.",
        annotation_format="Pixel segmentation masks (.gif) + FOV masks (.gif).",
        image_formats="TIFF (.tif) color fundus photographs; GIF (.gif) binary vessel & FOV masks.",
        image_dimensions="565 x 584 pixels (cropped FOV) / 768 x 584 context, 8-bit RGB, circular FOV ~540 px diameter.",
        camera_and_acquisition_specs="Canon CR5 non-mydriatic 3CCD fundus camera, 45-degree FOV, Netherlands diabetic screening program (patients aged 25-90).",
        patient_identifiers_available=False,
        patient_level_separation_possible=False,
        known_limitations_and_biases=(
            "Very small dataset (40 images) and low resolution (565x584) from a single Dutch Canon CR5 screening cohort (only 7 mild DR images, 0 severe/PDR). "
            "Unsuitable for DR severity classification training; strictly a retinal vessel tree segmentation benchmark."
        ),
        suitable_roles="Separate vascular segmentation / vessel caliber research and future anatomical optic/vascular interpretability validation only.",
        phase5_acquisition_status="investigated_access_pending",
        legitimate_acquisition_steps=(
            "1. Register/log in at https://drive.grand-challenge.org/. "
            "2. Accept Grand Challenge terms and download training/test ZIP packages. "
            "3. Extract into DATASET_ROOT/raw/drive/."
        ),
    ),
]


def export_dataset_inventory_csv(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(VERIFIED_DATASET_REGISTRY[0]).keys())
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for rec in VERIFIED_DATASET_REGISTRY:
            writer.writerow(asdict(rec))
    return output_path


def export_dataset_summary_json(output_path: Path, dataset_root: str) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "phase": "Phase 5 - Dataset Acquisition, Inspection & Preparation",
        "dataset_root_configured": dataset_root,
        "datasets_actually_downloaded": [],
        "datasets_only_investigated": [r.dataset_key for r in VERIFIED_DATASET_REGISTRY],
        "dataset_access_pending": [
            {
                "dataset_key": r.dataset_key,
                "display_name": r.display_name,
                "reason": r.access_gate_details,
                "commercial_use_status": r.commercial_use_status,
            }
            for r in VERIFIED_DATASET_REGISTRY
        ],
        "datasets": [asdict(r) for r in VERIFIED_DATASET_REGISTRY],
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    return output_path


def export_phase6_reports(
    csv_path: Path,
    json_path: Path,
    quality_audit_payload: dict,
    readiness_payload: dict,
) -> tuple[Path, Path]:
    """
    Export truthful, disk-verified Phase 6 dataset inventory CSV & summary JSON.
    Never invents downloaded counts or masks authorization blockers.
    """
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)

    readiness_by_key = {d["dataset_key"]: d for d in readiness_payload.get("datasets", [])}
    per_ds_metrics = quality_audit_payload.get("per_dataset_metrics", {})

    rows = []
    for meta in VERIFIED_DATASET_REGISTRY:
        ds = meta.dataset_key
        rd = readiness_by_key.get(ds, {})
        qm = per_ds_metrics.get(ds, {})
        row = asdict(meta)
        row["phase6_local_status"] = rd.get("phase6_status", "awaiting_authorization")
        row["preserved_archives_count"] = qm.get("preserved_archives_count", 0)
        row["raw_files_on_disk"] = qm.get("raw_files_on_disk", 0)
        row["inspected_accepted_images"] = qm.get("accepted_images", 0)
        row["inspected_rejected_images"] = qm.get("rejected_images", 0)
        row["inspected_exact_duplicates"] = qm.get("exact_duplicates_within_dataset", 0)
        row["inspected_missing_images"] = qm.get("missing_images", 0)
        row["inspected_missing_labels"] = qm.get("missing_labels", 0)
        row["verified_label_distribution"] = json.dumps(qm.get("label_distribution", {}))
        rows.append(row)

    fieldnames = list(rows[0].keys())
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)

    summary_payload = {
        "phase": "Phase 6 - Real Dataset Acquisition, Import & Validation",
        "audited_at_utc": quality_audit_payload.get("audited_at_utc"),
        "dataset_root_configured": readiness_payload.get("dataset_root"),
        "disk_free_gb": readiness_payload.get("disk_free_gb"),
        "disk_total_gb": readiness_payload.get("disk_total_gb"),
        "kaggle_credentials": readiness_payload.get("kaggle_credentials"),
        "datasets_actually_downloaded": quality_audit_payload.get("datasets_actually_downloaded", []),
        "datasets_extracted": quality_audit_payload.get("datasets_extracted", []),
        "datasets_inspected": quality_audit_payload.get("datasets_inspected", []),
        "datasets_awaiting_authorization": quality_audit_payload.get("datasets_awaiting_authorization", []),
        "datasets_with_quality_or_licensing_issues": quality_audit_payload.get(
            "datasets_with_quality_or_licensing_issues", []
        ),
        "cross_dataset_exact_duplicates": quality_audit_payload.get("cross_dataset_exact_duplicates", []),
        "cross_dataset_near_duplicates": quality_audit_payload.get("cross_dataset_near_duplicates", []),
        "dr_development_labeled_images_verified": quality_audit_payload.get(
            "dr_development_labeled_images_verified", 0
        ),
        "sufficient_for_model_development": quality_audit_payload.get("sufficient_for_model_development", False),
        "final_gate_reason": quality_audit_payload.get("final_gate_reason"),
        "datasets": rows,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary_payload, f, indent=2)

    return csv_path, json_path
