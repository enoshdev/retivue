"""
Practical End-to-End Smoke Test against live RETIVUE local server (http://127.0.0.1:8000)
"""

import io
import json
import uuid
import sys
import numpy as np
from PIL import Image
import httpx

BASE_URL = "http://127.0.0.1:8000"


def make_synthetic_fundus_bytes(size: int = 512, seed: int = 100) -> bytes:
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


def run_smoke_test():
    print("=" * 60)
    print("RETIVUE LIVE END-TO-END SMOKE TEST")
    print(f"Target: {BASE_URL}")
    print("=" * 60)

    client = httpx.Client(base_url=BASE_URL, timeout=60.0)

    # 1. Health checks
    print("\n[Step 1] Checking Service & Database Health...")
    r = client.get("/api/health")
    assert r.status_code == 200, f"Health failed: {r.status_code} {r.text}"
    h_data = r.json()
    print(f"  ✓ Service Health: {h_data['status']} ({h_data['project']} v{h_data['version']})")

    r = client.get("/api/health/database")
    assert r.status_code == 200, f"Database health failed: {r.status_code} {r.text}"
    db_data = r.json()
    print(f"  ✓ Database Health: {db_data['status']} ({db_data['database']} latency={db_data['latency_ms']:.1f}ms)")

    # 2. Registration & Authentication
    print("\n[Step 2] Authenticating Clinician...")
    unique = uuid.uuid4().hex[:6]
    email = f"dr_smoke_{unique}@retivue.hospital.org"
    password = "StrongPassword123!"

    r = client.post(
        "/api/auth/register",
        json={
            "full_name": f"Dr. SmokeTest {unique.upper()}",
            "email": email,
            "password": password,
            "facility_name": "Apex Vitreoretinal Institute",
            "registration_number": f"REG-{unique.upper()}",
        },
    )
    assert r.status_code == 201, f"Register failed: {r.status_code} {r.text}"
    user_data = r.json()["user"]
    print(f"  ✓ Registered: {user_data['full_name']} ({user_data['email']})")

    # Capture CSRF token
    csrf_token = client.cookies.get("retivue_csrf")
    headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}

    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200, f"Get current user failed: {r.status_code}"
    print(f"  ✓ Session verified via cookies: User ID {r.json()['id']}")

    # 3. AI Models Registry
    print("\n[Step 3] Inspecting Research AI Model Registry...")
    r = client.get("/api/workflow/ai-models", headers=headers)
    assert r.status_code == 200, f"List AI models failed: {r.status_code}"
    models = r.json()
    assert len(models) >= 3, f"Expected 3 models, got {len(models)}"
    for m in models:
        print(f"  ✓ Checkpoint: {m['model_key']} | Arch: {m['architecture']} | Epoch: {m['checkpoint_epoch']} | Available: {m['checkpoint_present']}")

    # 4. Patient Management & Informed Consent
    print("\n[Step 4] Creating Patient & Recording Consent...")
    r = client.post(
        "/api/patients",
        headers=headers,
        json={
            "full_name": f"Patient Beatrice {unique.upper()}",
            "patient_code": f"MRN-SMOKE-{unique.upper()}",
            "date_of_birth": "1969-08-14",
            "sex": "female",
            "diabetes_type": "type_2",
        },
    )
    assert r.status_code == 201, f"Create patient failed: {r.status_code} {r.text}"
    patient_id = r.json()["id"]
    mrn = r.json().get("patient_code", "N/A")
    print(f"  ✓ Patient Created: ID {patient_id} (Code: {mrn})")

    r = client.post(
        f"/api/patients/{patient_id}/consent",
        headers=headers,
        json={
            "consent_type": "retinal_screening",
            "consent_status": "granted",
            "form_version": "v2.1",
            "notes": "Electronic patient consent signed during clinical intake.",
        },
    )
    assert r.status_code == 201, f"Consent record failed: {r.status_code} {r.text}"
    print(f"  ✓ Consent Recorded: Status '{r.json()['consent_status']}'")

    # 5. Baseline Encounter (Screening 1)
    print("\n[Step 5] Creating Baseline Screening Encounter 1...")
    r = client.post(
        "/api/screenings",
        headers=headers,
        json={
            "patient_id": patient_id,
            "camera_model": "Topcon NW400 Non-Mydriatic Fundus Camera",
        },
    )
    assert r.status_code == 201, f"Create screening failed: {r.status_code} {r.text}"
    sc1_id = r.json()["id"]
    sc1_ref = r.json()["screening_reference"]
    print(f"  ✓ Encounter 1 Created: {sc1_ref} (ID: {sc1_id})")

    # Upload OD & OS images
    print("  ... Uploading bilateral fundus scans (OD & OS)")
    od_bytes_1 = make_synthetic_fundus_bytes(size=512, seed=101)
    os_bytes_1 = make_synthetic_fundus_bytes(size=512, seed=102)

    r_od = client.post(
        f"/api/screenings/{sc1_id}/images/OD",
        headers=headers,
        files={"file": ("fundus_od.jpg", od_bytes_1, "image/jpeg")},
    )
    assert r_od.status_code == 201, f"Upload OD failed: {r_od.status_code} {r_od.text}"

    r_os = client.post(
        f"/api/screenings/{sc1_id}/images/OS",
        headers=headers,
        files={"file": ("fundus_os.jpg", os_bytes_1, "image/jpeg")},
    )
    assert r_os.status_code == 201, f"Upload OS failed: {r_os.status_code} {r_os.text}"
    print("  ✓ OD and OS images stored in secure private storage.")

    # Submit screening
    r = client.post(f"/api/screenings/{sc1_id}/submit", headers=headers)
    assert r.status_code == 200, f"Submit failed: {r.status_code} {r.text}"
    print(f"  ✓ Encounter submitted. Lifecycle status: {r.json()['status']}")

    # Run AI screening
    print("  ... Running genuine EfficientNet-B0 inference on Encounter 1")
    r = client.post(f"/api/screenings/{sc1_id}/ai-run", headers=headers, json={})
    assert r.status_code == 200, f"AI run failed: {r.status_code} {r.text}"
    ai1_data = r.json()
    print(f"  ✓ AI Analysis Complete: Status={ai1_data['overall_status']}, Execution={ai1_data['execution_ms']:.1f}ms")
    for eye_res in ai1_data["eye_results"]:
        print(f"    - Eye {eye_res['eye']}: Grade {eye_res['predicted_grade']} ({eye_res['predicted_label']}) | Confidence={eye_res['confidence_max_prob']*100:.1f}% | VTDR={eye_res['vtdr_prob_sum']*100:.1f}%")

    # 6. Grad-CAM Explainability Artifacts
    print("\n[Step 6] Verifying Genuine Grad-CAM Artifacts for Encounter 1...")
    r = client.get(f"/api/screenings/{sc1_id}/explanations/OD", headers=headers)
    assert r.status_code == 200, f"Get explanation failed: {r.status_code} {r.text}"
    od_exp = r.json()
    print(f"  ✓ OD Explanation Record: Layer={od_exp['model_layer']}, Target Class={od_exp['target_class']} ({od_exp['target_class_label']})")
    print(f"    Narrative: \"{od_exp['explanation_text'][:90]}...\"")

    # Stream Heatmap and Overlay images
    r_hm = client.get(f"/api/screenings/{sc1_id}/explanations/OD/heatmap", headers=headers)
    assert r_hm.status_code == 200, f"Stream heatmap failed: {r_hm.status_code}"
    assert r_hm.headers["content-type"] == "image/png"
    print(f"  ✓ OD Transparent Heatmap: Streamed {len(r_hm.content)} bytes (image/png)")

    r_ov = client.get(f"/api/screenings/{sc1_id}/explanations/OD/overlay", headers=headers)
    assert r_ov.status_code == 200, f"Stream overlay failed: {r_ov.status_code}"
    assert r_ov.headers["content-type"] == "image/png"
    print(f"  ✓ OD Blended Grad-CAM Overlay: Streamed {len(r_ov.content)} bytes (image/png)")

    # 7. Follow-up Encounter & Longitudinal Comparison (Screening 2)
    print("\n[Step 7] Creating Follow-up Encounter 2 & Evaluating Longitudinal Comparison...")
    r = client.post(
        "/api/screenings",
        headers=headers,
        json={
            "patient_id": patient_id,
            "camera_model": "Topcon NW400 Non-Mydriatic Fundus Camera",
        },
    )
    assert r.status_code == 201, f"Create screening 2 failed: {r.status_code}"
    sc2_id = r.json()["id"]
    sc2_ref = r.json()["screening_reference"]

    od_bytes_2 = make_synthetic_fundus_bytes(size=512, seed=201)
    os_bytes_2 = make_synthetic_fundus_bytes(size=512, seed=202)
    client.post(f"/api/screenings/{sc2_id}/images/OD", headers=headers, files={"file": ("fundus_od2.jpg", od_bytes_2, "image/jpeg")})
    client.post(f"/api/screenings/{sc2_id}/images/OS", headers=headers, files={"file": ("fundus_os2.jpg", os_bytes_2, "image/jpeg")})
    client.post(f"/api/screenings/{sc2_id}/submit", headers=headers)
    r = client.post(f"/api/screenings/{sc2_id}/ai-run", headers=headers, json={})
    assert r.status_code == 200, f"AI run 2 failed: {r.status_code}"
    print(f"  ✓ Follow-up Encounter 2 Created & Analyzed: {sc2_ref}")

    # Longitudinal Comparison Request
    r = client.get(f"/api/screenings/{sc2_id}/comparison", headers=headers)
    assert r.status_code == 200, f"Comparison failed: {r.status_code} {r.text}"
    comp = r.json()
    print(f"  ✓ Comparison Result: Compared {comp['current_screening_reference']} against {comp['previous_screening_reference']}")
    print(f"    - Interval: {comp['days_interval']} days")
    print(f"    - OD Grade Delta: {comp['od_comparison']['grade_difference']} | Prior: {comp['od_comparison']['previous_label']} -> Current: {comp['od_comparison']['current_label']}")
    print(f"    - OS Grade Delta: {comp['os_comparison']['grade_difference']} | Prior: {comp['os_comparison']['previous_label']} -> Current: {comp['os_comparison']['current_label']}")
    print(f"    - Neutral Clinical Summary: {comp['od_comparison']['neutral_summary']}")

    # Patient Screening Timeline
    r = client.get(f"/api/patients/{patient_id}/timeline", headers=headers)
    assert r.status_code == 200, f"Timeline failed: {r.status_code}"
    timeline = r.json()
    print(f"  ✓ Patient Trajectory: {timeline['total_screenings']} encounters recorded")
    for evt in timeline["events"]:
        print(f"    - [{evt['trend_category'].upper()}] {evt['screening_reference']}: Worst Grade={evt['worst_grade']} ({evt['worst_label']}) | Review Status={evt['review_status']}")

    # 8. Download Official Vector PDF Report
    print("\n[Step 8] Generating & Streaming Official Clinical PDF Report...")
    r = client.get(f"/api/screenings/{sc2_id}/report/pdf", headers=headers)
    assert r.status_code == 200, f"PDF report generation failed: {r.status_code} {r.text}"
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment;" in r.headers.get("content-disposition", "")
    pdf_bytes = r.content
    assert pdf_bytes.startswith(b"%PDF-"), "File is not a valid PDF binary"
    print(f"  ✓ Official Medical PDF Generated: Streamed {len(pdf_bytes):,} bytes")
    print(f"    - Content-Type: {r.headers['content-type']}")
    print(f"    - Content-Disposition: {r.headers.get('content-disposition')}")

    print("\n" + "=" * 60)
    print("ALL 8 END-TO-END SMOKE TEST PHASES PASSED 100%!")
    print("=" * 60)


if __name__ == "__main__":
    run_smoke_test()
