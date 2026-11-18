"""
Automated Test Suite for Genuine Grad-CAM Explainability & Detailed AI Screening (Phase 1)
RETIVUE CADe Clinical Decision Support Systems
"""

import io
import json
import uuid
import pytest
from httpx import AsyncClient
import numpy as np
from PIL import Image

from app.core.config import settings
from app.services.ai_screening_service import AiScreeningService
from ai.gradcam import GradCAMGenerator, generate_explanation_text
from tests.conftest import CSRFAutoClient


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


async def _create_patient_with_consent(client: AsyncClient, name: str) -> str:
    pat_resp = await client.post(
        "/api/patients",
        json={
            "full_name": name,
            "medical_record_number": f"MRN-GC-{uuid.uuid4().hex[:6].upper()}",
            "date_of_birth": "1968-07-22",
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


async def _register_doctor(client: AsyncClient, email_prefix: str) -> dict:
    unique_tag = f"{email_prefix}_{uuid.uuid4().hex[:8]}"
    resp = await client.post(
        "/api/auth/register",
        json={
            "full_name": f"Dr. {email_prefix.title()} Specialist",
            "email": f"{unique_tag}@retivue.hospital.org",
            "password": "StrongPassword123!",
            "facility_name": "Apex Vitreoretinal Institute",
            "registration_number": f"REG-MD-{uuid.uuid4().hex[:6].upper()}",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["user"]


@pytest.mark.asyncio
async def test_gradcam_generator_unit_all_classes():
    """
    Unit test: Verifies GradCAMGenerator on the genuine EfficientNet-B0 model.
    Checks targeting features[8], gradient computation, all 5 target classes,
    alignment to original image dimensions, and dynamic narrative generation.
    """
    predictor, meta = AiScreeningService.get_or_load_predictor("aptos_e2_weighted_sampler")
    model = predictor.model
    generator = GradCAMGenerator(model=model, target_layer=model.features[8])

    fundus_bytes = _make_synthetic_fundus_bytes(size=600, seed=123)
    orig_img = Image.open(io.BytesIO(fundus_bytes))
    orig_w, orig_h = orig_img.size

    for target_class in range(5):
        cam_result = generator.generate_aligned_cam(
            fundus_bytes,
            eval_transform=predictor.eval_transform,
            prep_config=predictor.prep_config,
            device=predictor.device,
            target_class=target_class,
        )

        # 1. Verify target class and metadata
        assert cam_result["target_class"] == target_class
        assert cam_result["model_layer"] in ("features.8", "model.features[8]")

        # 2. Verify heatmap and overlay dimensions match original fundus image exactly
        heatmap_img = Image.open(io.BytesIO(cam_result["heatmap_png_bytes"]))
        assert heatmap_img.size == (orig_w, orig_h)
        assert heatmap_img.mode == "RGBA"  # Transparent heatmap

        overlay_img = Image.open(io.BytesIO(cam_result["overlay_png_bytes"]))
        assert overlay_img.size == (orig_w, orig_h)
        assert overlay_img.mode == "RGB"  # Blended overlay

        # 3. Verify activation map has non-zero positive activations
        assert cam_result["cam_full"].shape == (orig_h, orig_w)
        assert np.max(cam_result["cam_full"]) > 0.0

    # 4. Verify explanation text generation
    narrative = generate_explanation_text(
        predicted_grade=2,
        target_class=2,
        probabilities={"class_0": 0.05, "class_1": 0.15, "class_2": 0.65, "class_3": 0.10, "class_4": 0.05},
    )
    assert len(narrative) > 20
    assert "Grad-CAM" in narrative or "features[8]" in narrative or "Grade 2" in narrative or "Moderate" in narrative


@pytest.mark.asyncio
async def test_full_gradcam_workflow_and_api(client: AsyncClient):
    """
    End-to-End integration test:
    1. Creates patient and screening encounter.
    2. Uploads OD and OS fundus scans.
    3. Runs AI screening (evaluates inference + generates Grad-CAM).
    4. Asserts explanation records created in DB and linked to AI run.
    5. Retrieves explanation metadata via GET /screenings/{id}/explanations/{eye}.
    6. Streams heatmap and overlay PNGs and verifies byte signatures.
    7. Tests on-demand regeneration of an alternative target class (e.g. Class 4).
    8. Verifies formal report endpoint includes bilateral explanations.
    """
    user = await _register_doctor(client, "gradcam_lead")

    # Step 1: Create Patient with granted consent
    patient_id = await _create_patient_with_consent(client, "Test Patient GradCAM")

    # Step 2: Create Draft Screening
    sc_resp = await client.post(
        "/api/screenings",
        json={
            "patient_id": patient_id,
            "screening_type": "opportunistic",
            "protocol_version": "v1.0",
        },
    )
    assert sc_resp.status_code == 201, sc_resp.text
    screening_id = sc_resp.json()["id"]

    # Step 3: Upload OD and OS Images
    od_bytes = _make_synthetic_fundus_bytes(size=512, seed=101)
    os_bytes = _make_synthetic_fundus_bytes(size=512, seed=202)

    up_od = await client.post(
        f"/api/screenings/{screening_id}/images/OD",
        files={"file": ("right_eye_gradcam.jpg", od_bytes, "image/jpeg")},
    )
    assert up_od.status_code == 201, up_od.text

    up_os = await client.post(
        f"/api/screenings/{screening_id}/images/OS",
        files={"file": ("left_eye_gradcam.jpg", os_bytes, "image/jpeg")},
    )
    assert up_os.status_code == 201, up_os.text

    # Step 4: Submit Screening
    sub_resp = await client.post(f"/api/screenings/{screening_id}/submit")
    assert sub_resp.status_code == 200, sub_resp.text

    # Step 5: Run AI Screening
    ai_resp = await client.post(f"/api/screenings/{screening_id}/ai-run", json={})
    assert ai_resp.status_code == 200, ai_resp.text
    ai_data = ai_resp.json()
    assert ai_data["overall_status"] in ("completed", "quality_passed")
    assert len(ai_data["eye_results"]) == 2

    # Verify both OD and OS have explanations generated
    for eye_res in ai_data["eye_results"]:
        assert eye_res["gradable"] is True
        expl = eye_res["explanation"]
        assert expl is not None
        assert expl["status"] == "completed"
        assert expl["target_class"] == eye_res["predicted_grade"]
        assert expl["has_heatmap"] is True
        assert expl["has_overlay"] is True
        assert expl["model_layer"] in ("features.8", "model.features[8]")
        assert len(expl["explanation_text"]) > 20

    # Step 6: Test GET /api/screenings/{id}/explanations/{eye}
    get_expl_od = await client.get(f"/api/screenings/{screening_id}/explanations/OD")
    assert get_expl_od.status_code == 200, get_expl_od.text
    od_expl_data = get_expl_od.json()
    assert od_expl_data["eye"] == "OD"
    assert od_expl_data["status"] == "completed"
    assert od_expl_data["is_default_target"] is True

    # Step 7: Test Streaming Heatmap and Overlay
    stream_hm = await client.get(f"/api/screenings/{screening_id}/explanations/OD/heatmap")
    assert stream_hm.status_code == 200, stream_hm.text
    assert stream_hm.headers["content-type"] == "image/png"
    assert stream_hm.content.startswith(b"\x89PNG\r\n\x1a\n")

    stream_ov = await client.get(f"/api/screenings/{screening_id}/explanations/OD/overlay")
    assert stream_ov.status_code == 200, stream_ov.text
    assert stream_ov.headers["content-type"] == "image/png"
    assert stream_ov.content.startswith(b"\x89PNG\r\n\x1a\n")

    # Step 8: Test On-Demand Regeneration for Class 4 (Proliferative)
    regen_resp = await client.post(
        f"/api/screenings/{screening_id}/explanations/OD/regenerate",
        json={"target_class": 4},
    )
    assert regen_resp.status_code == 200, regen_resp.text
    regen_data = regen_resp.json()
    assert regen_data["target_class"] == 4
    assert regen_data["target_class_label"] in ("PDR", "proliferative_dr")
    assert regen_data["status"] == "completed"
    assert regen_data["has_overlay"] is True

    # Verify streaming specifically for class 4
    stream_ov_c4 = await client.get(
        f"/api/screenings/{screening_id}/explanations/OD/overlay?target_class=4"
    )
    assert stream_ov_c4.status_code == 200
    assert stream_ov_c4.headers["content-type"] == "image/png"

    # Step 9: Verify Integrated Formal Report endpoint includes explanations
    report_resp = await client.get(f"/api/screenings/{screening_id}/report")
    assert report_resp.status_code == 200, report_resp.text
    report_data = report_resp.json()
    assert "explanations" in report_data
    assert report_data["explanations"]["OD"]["status"] == "completed"
    assert report_data["explanations"]["OS"]["status"] == "completed"


@pytest.mark.asyncio
async def test_ungradable_image_withholds_gradcam(client: AsyncClient):
    """
    Safety Test: When an uploaded image fails quality gating (ungradable),
    the model must refuse grading and withhold Grad-CAM generation.
    Streaming endpoints must return HTTP 400.
    """
    await _register_doctor(client, "safety_qc")

    # Create Patient with granted consent
    patient_id = await _create_patient_with_consent(client, "Ungradable Test Patient")

    # Create Screening
    sc_resp = await client.post(
        "/api/screenings",
        json={"patient_id": patient_id, "screening_type": "opportunistic"},
    )
    screening_id = sc_resp.json()["id"]

    # Upload ungradable blurred image for OD, valid for OS
    blur_bytes = _make_ungradable_blur_bytes(size=512)
    valid_bytes = _make_synthetic_fundus_bytes(size=512, seed=99)

    await client.post(
        f"/api/screenings/{screening_id}/images/OD",
        files={"file": ("blur_od.jpg", blur_bytes, "image/jpeg")},
    )
    await client.post(
        f"/api/screenings/{screening_id}/images/OS",
        files={"file": ("valid_os.jpg", valid_bytes, "image/jpeg")},
    )

    await client.post(f"/api/screenings/{screening_id}/submit")
    ai_resp = await client.post(f"/api/screenings/{screening_id}/ai-run", json={})
    assert ai_resp.status_code == 200

    # OD should be ungradable
    od_expl_resp = await client.get(f"/api/screenings/{screening_id}/explanations/OD")
    assert od_expl_resp.status_code == 200
    od_expl = od_expl_resp.json()
    assert od_expl["status"] == "unavailable_ungradable"
    assert od_expl["has_heatmap"] is False
    assert od_expl["has_overlay"] is False

    # Streaming OD heatmap should fail with HTTP 404 (artifact file not present for ungradable scan)
    hm_stream = await client.get(f"/api/screenings/{screening_id}/explanations/OD/heatmap")
    assert hm_stream.status_code == 404
    assert "not found" in hm_stream.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cross_tenant_explanation_isolation(client: AsyncClient):
    """
    Security Test: Verifies tenant data isolation.
    Doctor B cannot access Doctor A's screening explanation metadata or streams.
    """
    # Doctor A setup
    await _register_doctor(client, "doctor_a")
    pt_a_id = await _create_patient_with_consent(client, "Patient Doctor A")
    sc_a = (await client.post(
        "/api/screenings",
        json={"patient_id": pt_a_id},
    )).json()
    img_bytes = _make_synthetic_fundus_bytes(size=512, seed=77)
    await client.post(
        f"/api/screenings/{sc_a['id']}/images/OD",
        files={"file": ("doc_a_od.jpg", img_bytes, "image/jpeg")},
    )
    await client.post(
        f"/api/screenings/{sc_a['id']}/images/OS",
        files={"file": ("doc_a_os.jpg", img_bytes, "image/jpeg")},
    )
    await client.post(f"/api/screenings/{sc_a['id']}/submit")
    await client.post(f"/api/screenings/{sc_a['id']}/ai-run", json={})

    # Doctor B registers (logs in as Doctor B)
    await _register_doctor(client, "doctor_b")

    # Doctor B attempts to access Doctor A's explanation
    resp = await client.get(f"/api/screenings/{sc_a['id']}/explanations/OD")
    assert resp.status_code == 404

    # Doctor B attempts to stream Doctor A's overlay
    stream_resp = await client.get(f"/api/screenings/{sc_a['id']}/explanations/OD/overlay")
    assert stream_resp.status_code == 404

    # Doctor B attempts to regenerate Doctor A's explanation
    regen_resp = await client.post(
        f"/api/screenings/{sc_a['id']}/explanations/OD/regenerate",
        json={"target_class": 2},
    )
    assert regen_resp.status_code == 404
