import io
import json
import uuid
import pytest
from httpx import AsyncClient
import numpy as np
from PIL import Image

from app.core.config import settings
from app.models.screening import Screening
from app.models.clinical_review import ClinicalReview
from app.models.referral import Referral
from tests.conftest import CSRFAutoClient, TestAsyncSessionLocal


def _make_synthetic_fundus_bytes(size: int = 512, seed: int = 42) -> bytes:
    """Creates a high-contrast synthetic fundus disk that passes retinal FOV and quality gates."""
    np.random.seed(seed)
    arr = np.zeros((size, size, 3), dtype=np.uint8)
    cy, cx = size // 2, size // 2
    radius = int(size * 0.44)
    yy, xx = np.ogrid[:size, :size]
    mask = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius ** 2

    # Retinal background color (deep orange-red)
    arr[mask, 0] = np.random.randint(180, 220, size=np.sum(mask))
    arr[mask, 1] = np.random.randint(70, 110, size=np.sum(mask))
    arr[mask, 2] = np.random.randint(25, 45, size=np.sum(mask))

    # Optic disc (bright yellow-white spot)
    disc_cy, disc_cx = cy, cx - int(radius * 0.45)
    disc_mask = (xx - disc_cx) ** 2 + (yy - disc_cy) ** 2 <= (int(radius * 0.18)) ** 2
    arr[disc_mask & mask, 0] = 240
    arr[disc_mask & mask, 1] = 210
    arr[disc_mask & mask, 2] = 130

    # Vessel structures (darker red lines)
    for i in range(-3, 4):
        vessel_y = np.clip(cy + i * 25, 0, size - 1)
        arr[vessel_y, cx - radius // 2 : cx + radius // 2, 0] = 110
        arr[vessel_y, cx - radius // 2 : cx + radius // 2, 1] = 30
        arr[vessel_y, cx - radius // 2 : cx + radius // 2, 2] = 15

    buf = io.BytesIO()
    Image.fromarray(arr, mode="RGB").save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _make_ungradable_blur_bytes(size: int = 512) -> bytes:
    """Creates a uniform dark/blurred image that triggers retinal quality rejection."""
    arr = np.full((size, size, 3), fill_value=12, dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr, mode="RGB").save(buf, format="JPEG", quality=90)
    return buf.getvalue()


async def _register_doctor(client: AsyncClient, email_prefix: str, reg_number: str = "REG-MD-12345") -> dict:
    unique_tag = f"{email_prefix}_{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/api/auth/register",
        json={
            "full_name": f"Dr. {email_prefix.title()}",
            "email": f"{unique_tag}@retivue.org",
            "password": "ValidPassword123!",
            "facility_name": "Eye Institute of Advanced Diagnostics",
            "registration_number": reg_number,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["user"]


async def _create_patient_with_consent(client: AsyncClient, name: str) -> str:
    pat_resp = await client.post(
        "/api/patients",
        json={
            "full_name": name,
            "patient_code": f"MRN-{name.upper().replace(' ', '-')}",
            "date_of_birth": "1972-04-15",
            "sex": "female",
            "diabetes_type": "Type 2",
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
            "witness_name": "Nurse Alex",
            "notes": "Patient informed consent verified.",
        },
    )
    assert consent_resp.status_code == 201, consent_resp.text
    return patient_id


@pytest.mark.asyncio
async def test_ai_model_registry_integrity_and_provenance(client: AsyncClient):
    """Verify that all frozen research checkpoints (E0, E1, E2) are registered with valid provenance."""
    user = await _register_doctor(client, "dr_prov")
    resp = await client.get("/api/workflow/ai-models")
    assert resp.status_code == 200, resp.text
    models = resp.json()
    assert len(models) == 3

    keys = {m["model_key"] for m in models}
    assert keys == {"aptos_e0_unweighted", "aptos_e1_weighted_effective", "aptos_e2_weighted_sampler"}

    for m in models:
        assert m["checkpoint_present"] is True
        assert len(m["checkpoint_sha256"]) == 64
        assert m["architecture"] == "efficientnet_b0"

    default_model = next(m for m in models if m["is_default"])
    assert default_model["model_key"] == "aptos_e2_weighted_sampler"


@pytest.mark.asyncio
async def test_end_to_end_screening_ai_review_referral_report_workflow(client: AsyncClient):
    """
    Complete end-to-end clinical workflow:
    1. Authorized clinician signs in.
    2. Register patient with granted consent.
    3. Create screening encounter.
    4. Upload bilateral (OD and OS) fundus images.
    5. Run quality-gated AI inference (records metadata, entropy, VTDR risk).
    6. Doctor conducts independent review and signs off with registration credential.
    7. AI re-run is blocked (cannot overwrite signed review).
    8. Doctor dispatches specialist referral linked to review.
    9. Retrieve comprehensive screening report and verify audit trail.
    """
    doctor = await _register_doctor(client, "dr_workflow", reg_number="MCI-2026-887711")
    patient_id = await _create_patient_with_consent(client, "Anita Sharma")

    # 1. Create screening
    scr_resp = await client.post("/api/screenings", json={"patient_id": patient_id})
    assert scr_resp.status_code == 201, scr_resp.text
    screening_id = scr_resp.json()["id"]

    # 2. Upload OD and OS images
    od_bytes = _make_synthetic_fundus_bytes(seed=101)
    os_bytes = _make_synthetic_fundus_bytes(seed=202)

    up_od = await client.post(
        f"/api/screenings/{screening_id}/images/OD",
        files={"file": ("right_eye.jpg", od_bytes, "image/jpeg")},
    )
    assert up_od.status_code == 201, up_od.text

    up_os = await client.post(
        f"/api/screenings/{screening_id}/images/OS",
        files={"file": ("left_eye.jpg", os_bytes, "image/jpeg")},
    )
    assert up_os.status_code == 201, up_os.text

    # 3. Submit for quality assessment
    sub_resp = await client.post(f"/api/screenings/{screening_id}/submit")
    assert sub_resp.status_code == 200, sub_resp.text
    assert sub_resp.json()["status"] == "ready_for_quality_assessment"

    # 4. Trigger AI screening inference
    ai_resp = await client.post(
        f"/api/screenings/{screening_id}/ai-run",
        json={"model_key": "aptos_e2_weighted_sampler"},
    )
    assert ai_resp.status_code == 200, ai_resp.text
    ai_run = ai_resp.json()

    assert ai_run["screening_id"] == screening_id
    assert ai_run["model_key"] == "aptos_e2_weighted_sampler"
    assert ai_run["checkpoint_sha256"] == "a94c4d0e2ac2e5200dabe6da122337f7a4191557dba5c02c85e52014b168686b"
    assert "research decision-support only" in ai_run["research_disclaimer"].lower()
    assert len(ai_run["eye_results"]) == 2

    for eye_res in ai_run["eye_results"]:
        assert eye_res["gradable"] is True
        assert eye_res["quality_status"] == "gradable"
        assert eye_res["predicted_grade"] in (0, 1, 2, 3, 4)
        assert eye_res["predicted_label"] is not None
        assert eye_res["normalized_entropy"] is not None
        assert 0.0 <= eye_res["normalized_entropy"] <= 1.0
        assert eye_res["vtdr_prob_sum"] is not None
        assert len(eye_res["probabilities"]) == 5

    # 5. Doctor signs independent clinical review
    review_resp = await client.post(
        f"/api/screenings/{screening_id}/review",
        json={
            "od_confirmed_grade": 1,
            "os_confirmed_grade": 2,
            "ai_agreement_status": "overrode_ai",
            "override_rationale": "Microaneurysms and hard exudates confirmed upon ophthalmoscopic magnification.",
            "clinical_findings": "Bilateral mild to moderate non-proliferative changes. Foveal avascular zone preserved.",
            "follow_up_plan": "Referral to retina clinic within 2 weeks for fluorescein angiography.",
            "recapture_required": False,
            "confirm_independent_review": True,
        },
    )
    assert review_resp.status_code == 201, review_resp.text
    review = review_resp.json()
    assert review["is_signed"] is True
    assert review["reviewer_name_snapshot"] == "Dr. Dr_Workflow"
    assert review["reviewer_registration_number_snapshot"] == "MCI-2026-887711"
    assert review["worst_eye_confirmed_grade"] == 2
    assert review["worst_eye_confirmed_label"] == "MODERATE_NPDR"

    # Verify screening status transitioned to clinically_reviewed_signed
    scr_check = await client.get(f"/api/screenings/{screening_id}")
    assert scr_check.status_code == 200
    assert scr_check.json()["status"] == "clinically_reviewed_signed"

    # 6. Safety check: AI re-run must be strictly rejected
    re_ai = await client.post(f"/api/screenings/{screening_id}/ai-run", json={})
    assert re_ai.status_code == 409
    assert "already exists" in re_ai.text

    # 7. Dispatch specialist referral
    ref_resp = await client.post(
        "/api/referrals",
        json={
            "screening_id": screening_id,
            "urgency": "WITHIN_2_WEEKS",
            "target_specialty": "Vitreoretinal Surgery & Medical Retina",
            "target_facility": "Apex Tertiary Eye Hospital",
            "reason_summary": "Moderate NPDR requiring macular OCT evaluation.",
            "clinical_summary": "Patient presented with type 2 diabetes. Independent assessment confirmed Grade 2 OS.",
        },
    )
    assert ref_resp.status_code == 201, ref_resp.text
    referral = ref_resp.json()
    assert referral["referral_reference"].startswith("REF-")
    assert referral["status"] == "DISPATCHED"
    assert referral["patient_name"] == "Anita Sharma"

    # 8. Retrieve complete clinical report
    report_resp = await client.get(f"/api/screenings/{screening_id}/report")
    assert report_resp.status_code == 200, report_resp.text
    report = report_resp.json()
    assert report["screening_id"] == screening_id
    assert report["screening_status"] == "clinically_reviewed_signed"
    assert report["patient"]["full_name"] == "Anita Sharma"
    assert report["clinical_review"]["worst_eye_confirmed_grade"] == 2
    assert len(report["referrals"]) == 1
    assert len(report["audit_trail"]) >= 3  # ai, review, referral
    assert "NOTICE" in report["clinical_safety_notice"]


@pytest.mark.asyncio
async def test_ungradable_image_refuses_forced_grade_and_escalates(client: AsyncClient):
    """
    Safety Rule: When an uploaded image fails the hardened quality gate,
    the model must NEVER force a DR grade, sets predicted_grade=None,
    and escalates the encounter to quality_failed_recapture_required.
    """
    await _register_doctor(client, "dr_quality", reg_number="MED-998877")
    patient_id = await _create_patient_with_consent(client, "Rahul Verma")

    scr = await client.post("/api/screenings", json={"patient_id": patient_id})
    assert scr.status_code == 201
    sid = scr.json()["id"]

    # Upload valid image for OD and blurred ungradable image for OS
    valid_bytes = _make_synthetic_fundus_bytes(seed=303)
    blur_bytes = _make_ungradable_blur_bytes()

    await client.post(f"/api/screenings/{sid}/images/OD", files={"file": ("od.jpg", valid_bytes, "image/jpeg")})
    await client.post(f"/api/screenings/{sid}/images/OS", files={"file": ("os_blur.jpg", blur_bytes, "image/jpeg")})
    await client.post(f"/api/screenings/{sid}/submit")

    ai_resp = await client.post(f"/api/screenings/{sid}/ai-run", json={})
    assert ai_resp.status_code == 200, ai_resp.text
    ai_run = ai_resp.json()

    assert ai_run["overall_status"] == "quality_failed"
    assert ai_run["overall_review_required"] is True

    os_res = next(e for e in ai_run["eye_results"] if e["eye"] == "OS")
    assert os_res["gradable"] is False
    assert os_res["predicted_grade"] is None
    assert os_res["predicted_label"] is None
    assert os_res["uncertainty_review_required"] is True
    assert os_res["quality_status"] in ("ungradable_image_quality", "decode_error")

    # Verify screening status was updated to quality_failed_recapture_required
    scr_check = await client.get(f"/api/screenings/{sid}")
    assert scr_check.json()["status"] == "quality_failed_recapture_required"


@pytest.mark.asyncio
async def test_revoked_consent_blocks_ai_inference(client: AsyncClient):
    """Safety Rule: Revoking consent blocks AI inference with 403 Forbidden."""
    await _register_doctor(client, "dr_consent", reg_number="MED-112233")
    patient_id = await _create_patient_with_consent(client, "Suresh Patel")

    scr = await client.post("/api/screenings", json={"patient_id": patient_id})
    sid = scr.json()["id"]

    valid_bytes = _make_synthetic_fundus_bytes()
    await client.post(f"/api/screenings/{sid}/images/OD", files={"file": ("od.jpg", valid_bytes, "image/jpeg")})
    await client.post(f"/api/screenings/{sid}/images/OS", files={"file": ("os.jpg", valid_bytes, "image/jpeg")})

    # Revoke patient consent
    rev_resp = await client.post(
        f"/api/patients/{patient_id}/consent",
        json={
            "consent_type": "retinal_screening",
            "consent_status": "revoked",
            "form_version": "v2.1",
            "notes": "Patient withdrew consent prior to analysis.",
        },
    )
    assert rev_resp.status_code == 201

    # Attempt AI inference
    ai_resp = await client.post(f"/api/screenings/{sid}/ai-run", json={})
    assert ai_resp.status_code == 403
    assert "revoked" in ai_resp.text or "consent" in ai_resp.text.lower()


@pytest.mark.asyncio
async def test_uncredentialed_user_cannot_sign_clinical_review(client: AsyncClient):
    """Safety Rule: A user without medical registration credentials cannot sign off clinical assessments."""
    # Register technician without registration_number
    reg_resp = await client.post(
        "/api/auth/register",
        json={
            "full_name": "Tech Alex",
            "email": f"tech_alex_{uuid.uuid4().hex[:8]}@retivue.org",
            "password": "ValidPassword123!",
            "facility_name": "Community Clinic",
            "registration_number": None,
        },
    )
    assert reg_resp.status_code == 201

    pat_resp = await client.post(
        "/api/patients",
        json={"full_name": "Devi Rao", "patient_code": "MRN-DEVI", "sex": "female"},
    )
    pat_id = pat_resp.json()["id"]
    await client.post(
        f"/api/patients/{pat_id}/consent",
        json={"consent_type": "retinal_screening", "consent_status": "granted", "form_version": "v1"},
    )

    scr = await client.post("/api/screenings", json={"patient_id": pat_id})
    sid = scr.json()["id"]

    # Attempt to sign review
    review_resp = await client.post(
        f"/api/screenings/{sid}/review",
        json={
            "od_confirmed_grade": 0,
            "os_confirmed_grade": 0,
            "ai_agreement_status": "independent_no_ai",
            "clinical_findings": "Normal fundus appearance bilaterally.",
            "follow_up_plan": "Annual screening in 12 months.",
            "recapture_required": False,
            "confirm_independent_review": True,
        },
    )
    assert review_resp.status_code == 403
    assert "registration number" in review_resp.text.lower()


@pytest.mark.asyncio
async def test_cross_account_isolation_for_clinical_workflow(client: AsyncClient):
    """Safety Rule: Screenings, AI runs, reviews, and referrals are strictly isolated across user accounts."""
    doc_a = await _register_doctor(client, "dr_user_a", reg_number="REG-A-001")
    pat_a_id = await _create_patient_with_consent(client, "Patient Alpha")
    scr_a = await client.post("/api/screenings", json={"patient_id": pat_a_id})
    sid_a = scr_a.json()["id"]

    # Doctor B registers and logs in
    await client.post("/api/auth/logout")
    doc_b = await _register_doctor(client, "dr_user_b", reg_number="REG-B-002")

    # Doctor B tries to access Doctor A's screening, AI runs, review, and report
    assert (await client.get(f"/api/screenings/{sid_a}")).status_code == 404
    assert (await client.post(f"/api/screenings/{sid_a}/ai-run", json={})).status_code == 404
    assert (await client.get(f"/api/screenings/{sid_a}/ai-runs")).status_code == 200
    assert len((await client.get(f"/api/screenings/{sid_a}/ai-runs")).json()) == 0
    assert (await client.get(f"/api/screenings/{sid_a}/report")).status_code == 404
    assert (await client.get(f"/api/screenings/{sid_a}/audit")).status_code == 404
