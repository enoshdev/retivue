"""
Automated Test Suite for Longitudinal Screening Comparison & Patient PDF Reports (Phase 2)
RETIVUE CADe Clinical Decision Support Systems
"""

import io
import uuid
import pytest
from httpx import AsyncClient
import numpy as np
from PIL import Image

from app.services.pdf_report_service import PdfReportService


def _make_synthetic_fundus_bytes(size: int = 512, seed: int = 42) -> bytes:
    """Creates a high-contrast synthetic fundus disk that passes retinal FOV and quality gates."""
    np.random.seed(seed)
    arr = np.zeros((size, size, 3), dtype=np.uint8)
    cy, cx = size // 2, size // 2
    radius = int(size * 0.44)
    yy, xx = np.ogrid[:size, :size]
    mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius ** 2

    arr[mask, 0] = np.random.randint(180, 220, size=np.sum(mask))
    arr[mask, 1] = np.random.randint(70, 110, size=np.sum(mask))
    arr[mask, 2] = np.random.randint(25, 45, size=np.sum(mask))

    disc_cy, disc_cx = cy, cx - int(radius * 0.45)
    disc_mask = (xx - disc_cx) ** 2 + (yy - disc_cy) ** 2 <= (int(radius * 0.18)) ** 2
    arr[disc_mask & mask, 0] = 240
    arr[disc_mask & mask, 1] = 210
    arr[disc_mask & mask, 2] = 130

    for i in range(-3, 4):
        vessel_y = np.clip(cy + i * 25, 0, size - 1)
        arr[vessel_y, cx - radius // 2 : cx + radius // 2, 0] = 110
        arr[vessel_y, cx - radius // 2 : cx + radius // 2, 1] = 30
        arr[vessel_y, cx - radius // 2 : cx + radius // 2, 2] = 15

    buf = io.BytesIO()
    Image.fromarray(arr, mode="RGB").save(buf, format="JPEG", quality=95)
    return buf.getvalue()


async def _register_doctor(client: AsyncClient, prefix: str) -> dict:
    unique_tag = f"{prefix}_{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/api/auth/register",
        json={
            "full_name": f"Dr. {prefix.title()} Longitudinal",
            "email": f"{unique_tag}@retivue.hospital.org",
            "password": "StrongPassword123!",
            "facility_name": "Apex Vitreoretinal Institute",
            "registration_number": f"REG-MD-{uuid.uuid4().hex[:6].upper()}",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["user"]


async def _create_patient_with_consent(client: AsyncClient, name: str) -> str:
    pat_resp = await client.post(
        "/api/patients",
        json={
            "full_name": name,
            "medical_record_number": f"MRN-LONG-{uuid.uuid4().hex[:6].upper()}",
            "date_of_birth": "1972-04-15",
            "gender": "female",
            "diabetes_type": "type_2",
            "consent_status": "granted",
        },
    )
    assert pat_resp.status_code == 201, pat_resp.text
    patient_id = pat_resp.json()["id"]

    consent_resp = await client.post(
        f"/api/patients/{patient_id}/consent",
        json={
            "consent_type": "retinal_screening",
            "consent_status": "granted",
            "form_version": "v2.1",
            "notes": "Patient informed consent verified.",
        },
    )
    assert consent_resp.status_code == 201, consent_resp.text
    return patient_id


async def _create_and_populate_screening(
    client: AsyncClient,
    patient_id: str,
    camera_model: str = "Canon CR-2 AF",
) -> str:
    sc_resp = await client.post(
        "/api/screenings",
        json={
            "patient_id": patient_id,
            "camera_model": camera_model,
        },
    )
    assert sc_resp.status_code == 201, sc_resp.text
    screening_id = sc_resp.json()["id"]

    od_bytes = _make_synthetic_fundus_bytes(size=512, seed=10)
    os_bytes = _make_synthetic_fundus_bytes(size=512, seed=20)

    r_od = await client.post(
        f"/api/screenings/{screening_id}/images/OD",
        files={"file": ("fundus_od.jpg", od_bytes, "image/jpeg")},
    )
    assert r_od.status_code == 201, r_od.text

    r_os = await client.post(
        f"/api/screenings/{screening_id}/images/OS",
        files={"file": ("fundus_os.jpg", os_bytes, "image/jpeg")},
    )
    assert r_os.status_code == 201, r_os.text

    sub_resp = await client.post(f"/api/screenings/{screening_id}/submit")
    assert sub_resp.status_code == 200, sub_resp.text

    return screening_id


def test_pdf_report_service_direct_generation():
    """Unit test: Verifies ReportLab Platypus PDF generation with sample medical report data."""
    report_data = {
        "report_id": "RPT-UNITTEST-20261116",
        "screening_reference": "SCR-UNIT01",
        "generated_at": "2026-11-16T01:00:00Z",
        "screening_date": "2026-11-16T01:00:00Z",
        "screening_status": "reviewed",
        "patient": {
            "id": "pat_001",
            "full_name": "Eleanor Vance",
            "medical_record_number": "MRN-EV-9821",
            "date_of_birth": "1965-03-12",
            "gender": "female",
            "diabetes_type": "type_2",
        },
        "consent": {
            "status": "granted",
            "obtained_at": "2026-11-16T00:50:00Z",
            "capture_method": "electronic_signature",
        },
        "latest_ai_run": {
            "id": "run_001",
            "model_key": "efficientnet_b0_e2",
            "model_version": "v1.0",
            "architecture": "EfficientNet-B0",
            "checkpoint_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "checkpoint_epoch": 2,
            "overall_status": "completed",
            "highest_predicted_grade": 2,
            "highest_predicted_label": "Moderate NPDR",
            "higher_risk_eye": "OD",
            "overall_review_required": True,
            "overall_escalation_reasons": ["Estimated Moderate NPDR in right eye"],
            "inference_timestamp": "2026-11-16T01:00:00Z",
            "eye_results": [
                {
                    "eye": "OD",
                    "gradable": True,
                    "predicted_grade": 2,
                    "predicted_label": "Moderate NPDR",
                    "confidence": 0.88,
                    "class_probabilities": {"0": 0.05, "1": 0.07, "2": 0.72, "3": 0.12, "4": 0.04},
                    "referable_dr": True,
                    "vtdr_risk_prob": 0.16,
                    "review_required": True,
                    "uncertainty_reasons": [],
                },
                {
                    "eye": "OS",
                    "gradable": True,
                    "predicted_grade": 1,
                    "predicted_label": "Mild NPDR",
                    "confidence": 0.82,
                    "class_probabilities": {"0": 0.12, "1": 0.75, "2": 0.09, "3": 0.03, "4": 0.01},
                    "referable_dr": False,
                    "vtdr_risk_prob": 0.04,
                    "review_required": False,
                    "uncertainty_reasons": [],
                },
            ],
        },
        "clinical_review": {
            "reviewer_name": "Dr. Sarah Lin, MD",
            "reviewer_role": "retina_specialist",
            "reviewed_at": "2026-11-16T01:05:00Z",
            "agreement_status": "agreed_with_ai",
            "agreed_od_grade": 2,
            "agreed_os_grade": 1,
            "findings_summary": "Microaneurysms and hard exudates present in right eye. Mild scattered red lesions in left.",
            "follow_up_recommendation": "Follow-up surveillance in 6 months.",
        },
        "referrals": [
            {
                "referral_reference": "REF-001",
                "urgency": "WITHIN_2_WEEKS",
                "target_specialty": "Vitreoretinal Specialist",
                "target_facility": "Apex Eye Institute",
                "reason_summary": "Moderate NPDR with macular proximity evaluation required.",
                "status": "DISPATCHED",
            }
        ],
        "clinical_safety_notice": "NOTICE: auxiliary decision-support only. Final clinical diagnosis by MD.",
    }

    comparison_data = {
        "previous_screening_reference": "SCR-PRIOR01",
        "previous_screening_date": "2026-05-10T00:00:00Z",
        "days_interval": 190,
        "is_directly_comparable": True,
        "comparability_notes": [],
        "od_comparison": {
            "previous_grade": 1,
            "previous_label": "Mild NPDR",
            "current_grade": 2,
            "current_label": "Moderate NPDR",
            "grade_difference": 1,
            "vtdr_risk_shift": 0.08,
            "neutral_summary": "OD: AI-estimated grade increased (+1; Mild NPDR -> Moderate NPDR; requires clinical review).",
        },
        "os_comparison": {
            "previous_grade": 1,
            "previous_label": "Mild NPDR",
            "current_grade": 1,
            "current_label": "Mild NPDR",
            "grade_difference": 0,
            "vtdr_risk_shift": -0.01,
            "neutral_summary": "OS: No recorded grade change (Mild NPDR -> Mild NPDR, delta 0).",
        },
    }

    raw_fundus = _make_synthetic_fundus_bytes(size=256, seed=1)
    image_bytes_map = {
        "OD_original": raw_fundus,
        "OD_overlay": raw_fundus,
        "OS_original": raw_fundus,
        "OS_overlay": raw_fundus,
    }

    pdf_bytes = PdfReportService.generate_pdf(
        report_data=report_data,
        comparison_data=comparison_data,
        image_bytes_map=image_bytes_map,
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 5000
    assert pdf_bytes.startswith(b"%PDF-")


@pytest.mark.asyncio
async def test_longitudinal_comparison_and_pdf_api_flow(client: AsyncClient):
    """
    Integration test:
    1. Register Doctor & create Patient A
    2. Upload Baseline Screening 1 and run AI
    3. Upload Follow-up Screening 2 and run AI
    4. Call GET /screenings/{screening2_id}/comparison (auto and explicit)
    5. Test rejection of cross-patient comparison (400)
    6. Test rejection of same-screening comparison (400)
    7. Call GET /patients/{patient_a_id}/timeline
    8. Call GET /screenings/{screening2_id}/report/pdf and verify PDF bytes
    9. Test cross-account isolation with Doctor B (404)
    """
    # 1. Doctor A & Patient A
    await _register_doctor(client, "dr_a")
    patient_a = await _create_patient_with_consent(client, "Patient Alice Smith")

    # 2. Baseline Screening 1
    sc1_id = await _create_and_populate_screening(client, patient_a)
    ai1_resp = await client.post(f"/api/screenings/{sc1_id}/ai-run", json={})
    assert ai1_resp.status_code == 200, ai1_resp.text

    # 3. Follow-up Screening 2
    sc2_id = await _create_and_populate_screening(client, patient_a)
    ai2_resp = await client.post(f"/api/screenings/{sc2_id}/ai-run", json={})
    assert ai2_resp.status_code == 200, ai2_resp.text

    # 4. Compare Screenings (Auto-prior)
    comp_auto = await client.get(f"/api/screenings/{sc2_id}/comparison")
    assert comp_auto.status_code == 200, comp_auto.text
    comp_data = comp_auto.json()
    assert comp_data["patient_id"] == patient_a
    assert comp_data["current_screening_id"] == sc2_id
    assert comp_data["previous_screening_id"] == sc1_id
    assert "od_comparison" in comp_data
    assert "os_comparison" in comp_data
    assert comp_data["od_comparison"]["has_previous_image"] is True
    assert comp_data["od_comparison"]["has_current_image"] is True
    assert comp_data["is_directly_comparable"] is True
    assert "neutral_summary" in comp_data["od_comparison"]
    assert "clinical_safety_disclaimer" in comp_data

    # Compare Screenings (Explicit prior ID)
    comp_exp = await client.get(f"/api/screenings/{sc2_id}/comparison?previous_screening_id={sc1_id}")
    assert comp_exp.status_code == 200, comp_exp.text

    # 5. Cross-Patient Rejection
    patient_b = await _create_patient_with_consent(client, "Patient Bob Jones")
    sc3_id = await _create_and_populate_screening(client, patient_b)
    comp_cross = await client.get(f"/api/screenings/{sc2_id}/comparison?previous_screening_id={sc3_id}")
    assert comp_cross.status_code == 400
    assert "Cross-patient comparison forbidden" in comp_cross.json()["detail"]

    # 6. Same-Screening Rejection
    comp_same = await client.get(f"/api/screenings/{sc2_id}/comparison?previous_screening_id={sc2_id}")
    assert comp_same.status_code == 400
    assert "Cannot compare a screening with itself" in comp_same.json()["detail"]

    # 7. Patient Timeline
    timeline_resp = await client.get(f"/api/patients/{patient_a}/timeline")
    assert timeline_resp.status_code == 200, timeline_resp.text
    t_data = timeline_resp.json()
    assert t_data["patient_id"] == patient_a
    assert t_data["total_screenings"] == 2
    assert len(t_data["events"]) == 2
    assert t_data["events"][0]["screening_id"] == sc1_id
    assert t_data["events"][0]["trend_category"] == "baseline"
    assert t_data["events"][1]["screening_id"] == sc2_id
    assert t_data["events"][1]["trend_category"] in ("stable", "higher_grade", "lower_grade", "unassessed")
    assert "clinical_safety_notice" in t_data

    # 8. PDF Report Streaming
    pdf_resp = await client.get(f"/api/screenings/{sc2_id}/report/pdf")
    assert pdf_resp.status_code == 200, pdf_resp.text
    assert pdf_resp.headers["content-type"] == "application/pdf"
    assert "attachment;" in pdf_resp.headers.get("content-disposition", "")
    pdf_content = pdf_resp.content
    assert pdf_content.startswith(b"%PDF-")
    assert len(pdf_content) > 5000

    # 9. Cross-Account Isolation
    await _register_doctor(client, "dr_b")
    # Doctor B cannot view Doctor A's comparison
    iso_comp = await client.get(f"/api/screenings/{sc2_id}/comparison")
    assert iso_comp.status_code == 404

    # Doctor B cannot view Doctor A's timeline
    iso_time = await client.get(f"/api/patients/{patient_a}/timeline")
    assert iso_time.status_code == 404

    # Doctor B cannot download Doctor A's PDF
    iso_pdf = await client.get(f"/api/screenings/{sc2_id}/report/pdf")
    assert iso_pdf.status_code == 404
