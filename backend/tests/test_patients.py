import uuid
import pytest
from httpx import AsyncClient
from datetime import date
from sqlalchemy import text


async def _register_and_login(client: AsyncClient, email: str, full_name: str = "Test Clinician") -> dict:
    """Helper to register (or login) and establish authenticated session."""
    csrf_res = await client.get("/api/auth/csrf")
    assert csrf_res.status_code == 200
    csrf_token = csrf_res.json()["csrf_token"]

    reg_payload = {
        "full_name": full_name,
        "email": email,
        "password": "SecureTestPassword123!",
        "facility_name": "Test Retina Clinic",
        "registration_number": "MCI-12345"
    }
    reg_res = await client.post(
        "/api/auth/register",
        json=reg_payload,
        headers={"X-CSRF-Token": csrf_token}
    )
    if reg_res.status_code == 201:
        return reg_res.json()["user"]
    elif reg_res.status_code == 409:
        login_res = await client.post(
            "/api/auth/login",
            json={"email": email, "password": "SecureTestPassword123!"},
            headers={"X-CSRF-Token": csrf_token}
        )
        assert login_res.status_code == 200
        return login_res.json()["user"]
    assert reg_res.status_code == 201
    return reg_res.json()["user"]


@pytest.mark.asyncio
async def test_unauthenticated_patient_requests_rejected(client: AsyncClient):
    """Verify endpoints reject unauthenticated access with 401."""
    res = await client.get("/api/patients")
    assert res.status_code == 401
    assert "detail" in res.json()

    res_post = await client.post("/api/patients", json={"full_name": "Ghost Patient"})
    assert res_post.status_code == 401


@pytest.mark.asyncio
async def test_create_and_retrieve_patient(client: AsyncClient):
    """Verify creating a patient and retrieving it by ID."""
    user = await _register_and_login(client, f"dr.intake.{uuid.uuid4().hex[:6]}@retivue.org")

    payload = {
        "full_name": "Sunita Devi",
        "patient_code": "MRN-2026-001",
        "date_of_birth": "1968-04-15",
        "sex": "female",
        "contact_number": "+91 98765 43210",
        "diabetes_type": "Type 2",
        "diabetes_duration_years": 8,
        "recent_hba1c": "7.8%",
        "notes": "Patient reports mild blurring in right eye",
        "initial_consent": {
            "consent_type": "retinal_screening",
            "consent_status": "granted",
            "capture_method": "digital_acknowledgement",
            "notes": "Signed digitally during tablet intake"
        }
    }

    create_res = await client.post("/api/patients", json=payload)
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["full_name"] == "Sunita Devi"
    assert created["patient_code"] == "MRN-2026-001"
    assert created["owner_user_id"] == user["id"]
    assert created["is_archived"] is False
    assert created["active_consent"] is not None
    assert created["active_consent"]["consent_status"] == "granted"

    # Retrieve by ID
    get_res = await client.get(f"/api/patients/{created['id']}")
    assert get_res.status_code == 200
    retrieved = get_res.json()
    assert retrieved["id"] == created["id"]
    assert retrieved["full_name"] == "Sunita Devi"
    assert retrieved["active_consent"]["consent_status"] == "granted"


@pytest.mark.asyncio
async def test_optional_fields_and_duplicate_names(client: AsyncClient):
    """Verify patients can be created with only minimal required fields and duplicate names are permitted."""
    await _register_and_login(client, f"dr.intake.opt.{uuid.uuid4().hex[:6]}@retivue.org")

    # Patient 1: only full_name
    res1 = await client.post("/api/patients", json={"full_name": "Amit Kumar"})
    assert res1.status_code == 201
    p1 = res1.json()
    assert p1["patient_code"] is None
    assert p1["date_of_birth"] is None
    assert p1["active_consent"] is None

    # Patient 2: same name, different record
    res2 = await client.post("/api/patients", json={"full_name": "Amit Kumar", "patient_code": "MRN-DIFF-01"})
    assert res2.status_code == 201
    p2 = res2.json()
    assert p1["id"] != p2["id"]
    assert p2["full_name"] == "Amit Kumar"


@pytest.mark.asyncio
async def test_invalid_patient_data_rejected(client: AsyncClient):
    """Verify invalid payloads (empty name, invalid age) are rejected with 422."""
    await _register_and_login(client, f"dr.validator.{uuid.uuid4().hex[:6]}@retivue.org")

    # Empty name
    res = await client.post("/api/patients", json={"full_name": ""})
    assert res.status_code == 422

    # Negative diabetes duration
    res_neg = await client.post("/api/patients", json={"full_name": "Valid Name", "diabetes_duration_years": -5})
    assert res_neg.status_code == 422


@pytest.mark.asyncio
async def test_update_patient(client: AsyncClient):
    """Verify PATCH updates permitted fields and preserves ownership."""
    user = await _register_and_login(client, f"dr.updater.{uuid.uuid4().hex[:6]}@retivue.org")

    create_res = await client.post("/api/patients", json={"full_name": "Original Name"})
    patient_id = create_res.json()["id"]

    update_payload = {
        "full_name": "Updated Name",
        "patient_code": "MRN-UPDATED-99",
        "recent_hba1c": "6.5%"
    }
    patch_res = await client.patch(f"/api/patients/{patient_id}", json=update_payload)
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["full_name"] == "Updated Name"
    assert updated["patient_code"] == "MRN-UPDATED-99"
    assert updated["recent_hba1c"] == "6.5%"
    assert updated["owner_user_id"] == user["id"]


@pytest.mark.asyncio
async def test_archive_and_unarchive_patient(client: AsyncClient):
    """Verify soft-archiving patient and filtered listing."""
    await _register_and_login(client, f"dr.archiver.{uuid.uuid4().hex[:6]}@retivue.org")

    create_res = await client.post("/api/patients", json={"full_name": "Patient to Archive"})
    patient_id = create_res.json()["id"]

    # Archive
    arch_res = await client.post(f"/api/patients/{patient_id}/archive")
    assert arch_res.status_code == 200
    assert arch_res.json()["is_archived"] is True

    # Active listing should NOT include archived patient
    list_active = await client.get("/api/patients")
    assert not any(p["id"] == patient_id for p in list_active.json()["items"])

    # Listing with include_archived=true SHOULD include it
    list_all = await client.get("/api/patients?include_archived=true")
    assert any(p["id"] == patient_id for p in list_all.json()["items"])

    # Unarchive
    unarch_res = await client.post(f"/api/patients/{patient_id}/unarchive")
    assert unarch_res.status_code == 200
    assert unarch_res.json()["is_archived"] is False

    # Now appears in active listing again
    list_active2 = await client.get("/api/patients")
    assert any(p["id"] == patient_id for p in list_active2.json()["items"])


@pytest.mark.asyncio
async def test_search_and_pagination(client: AsyncClient):
    """Verify search by name, code, contact number, and pagination."""
    await _register_and_login(client, f"dr.searcher.{uuid.uuid4().hex[:6]}@retivue.org")

    # Create 5 distinct patients
    names = ["Ramesh Gupta", "Suresh Verma", "Geeta Sharma", "Pooja Patel", "Rameshwar Rao"]
    for i, name in enumerate(names):
        await client.post("/api/patients", json={
            "full_name": name,
            "patient_code": f"MRN-SEARCH-{i:03d}",
            "contact_number": f"980000000{i}"
        })

    # Search for "Ramesh" (should find Ramesh Gupta and Rameshwar Rao)
    search_res = await client.get("/api/patients?query=Ramesh")
    assert search_res.status_code == 200
    data = search_res.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2

    # Search by code
    code_res = await client.get("/api/patients?query=SEARCH-003")
    assert code_res.status_code == 200
    assert code_res.json()["total"] == 1
    assert code_res.json()["items"][0]["full_name"] == "Pooja Patel"

    # Pagination: page_size=2
    page1 = await client.get("/api/patients?page=1&page_size=2")
    assert page1.status_code == 200
    p1_data = page1.json()
    assert len(p1_data["items"]) == 2
    assert p1_data["total"] == 5
    assert p1_data["total_pages"] == 3


@pytest.mark.asyncio
async def test_consent_lifecycle_and_audit_history(client: AsyncClient):
    """Verify recording, revoking, and history of informed consent audit trail."""
    await _register_and_login(client, f"dr.consent.{uuid.uuid4().hex[:6]}@retivue.org")

    # Create patient with initial pending consent
    create_res = await client.post("/api/patients", json={
        "full_name": "Consent Test Subject",
        "initial_consent": {
            "consent_type": "retinal_screening",
            "consent_status": "pending",
            "capture_method": "written_form",
            "notes": "Intake form handed to patient"
        }
    })
    patient_id = create_res.json()["id"]

    # Record granted consent
    grant_res = await client.post(f"/api/patients/{patient_id}/consent", json={
        "consent_type": "retinal_screening",
        "consent_status": "granted",
        "capture_method": "written_form",
        "notes": "Patient returned signed paper consent"
    })
    assert grant_res.status_code == 201
    assert grant_res.json()["consent_status"] == "granted"

    # Revoke consent
    revoke_res = await client.post(f"/api/patients/{patient_id}/consent/revoke", json={
        "notes": "Patient withdrew consent before imaging"
    })
    assert revoke_res.status_code == 200
    assert revoke_res.json()["consent_status"] == "revoked"
    assert revoke_res.json()["revoked_at"] is not None

    # Retrieve full history (must contain all 3 events)
    hist_res = await client.get(f"/api/patients/{patient_id}/consent")
    assert hist_res.status_code == 200
    history = hist_res.json()
    assert len(history) == 3
    statuses = [c["consent_status"] for c in history]
    assert statuses == ["revoked", "granted", "pending"]


# ==============================================================================
# CRITICAL CROSS-ACCOUNT SECURITY AND ISOLATION TESTS
# ==============================================================================

@pytest.mark.asyncio
async def test_cross_account_isolation_user_a_and_user_b():
    """
    MANDATORY SECURITY TEST:
    Create User A and User B with independent sessions.
    Create Patient A under User A, and Patient B under User B.
    Verify that User A cannot read, search, list, update, archive, or access consent of Patient B.
    And vice versa.
    """
    from httpx import ASGITransport
    from app.main import app
    from tests.conftest import CSRFAutoClient

    transport = ASGITransport(app=app)
    async with CSRFAutoClient(transport=transport, base_url="http://test") as client_a:
        async with CSRFAutoClient(transport=transport, base_url="http://test") as client_b:
            # 1. Register User A
            user_a = await _register_and_login(client_a, f"user.a.{uuid.uuid4().hex[:6]}@clinic.org", "Dr. User A")

            # 2. Register User B
            user_b = await _register_and_login(client_b, f"user.b.{uuid.uuid4().hex[:6]}@clinic.org", "Dr. User B")
            assert user_a["id"] != user_b["id"]

            # 3. User A creates Patient A
            res_pa = await client_a.post("/api/patients", json={
                "full_name": "Patient Alpha (User A)",
                "patient_code": "ALPHA-001"
            })
            assert res_pa.status_code == 201
            patient_a_id = res_pa.json()["id"]

            # 4. User B creates Patient B
            res_pb = await client_b.post("/api/patients", json={
                "full_name": "Patient Beta (User B)",
                "patient_code": "BETA-001"
            })
            assert res_pb.status_code == 201
            patient_b_id = res_pb.json()["id"]

            # 5. User A can retrieve Patient A; User B can retrieve Patient B
            get_pa = await client_a.get(f"/api/patients/{patient_a_id}")
            assert get_pa.status_code == 200
            assert get_pa.json()["full_name"] == "Patient Alpha (User A)"

            get_pb = await client_b.get(f"/api/patients/{patient_b_id}")
            assert get_pb.status_code == 200
            assert get_pb.json()["full_name"] == "Patient Beta (User B)"

            # 6. User A CANNOT retrieve Patient B (Returns 404, not 403, preventing IDOR leakage)
            idor_res = await client_a.get(f"/api/patients/{patient_b_id}")
            assert idor_res.status_code == 404
            assert idor_res.json()["detail"] == "Patient record not found."

            # 7. User B CANNOT retrieve Patient A
            idor_res2 = await client_b.get(f"/api/patients/{patient_a_id}")
            assert idor_res2.status_code == 404

            # 8. User A CANNOT update Patient B
            hack_update = await client_a.patch(f"/api/patients/{patient_b_id}", json={
                "full_name": "Compromised Name"
            })
            assert hack_update.status_code == 404

            # Confirm Patient B was not modified
            verify_b = await client_b.get(f"/api/patients/{patient_b_id}")
            assert verify_b.json()["full_name"] == "Patient Beta (User B)"

            # 9. User A CANNOT archive Patient B
            hack_arch = await client_a.post(f"/api/patients/{patient_b_id}/archive")
            assert hack_arch.status_code == 404

            # 10. User A CANNOT view or add consent to Patient B
            hack_consent_view = await client_a.get(f"/api/patients/{patient_b_id}/consent")
            assert hack_consent_view.status_code == 404

            hack_consent_post = await client_a.post(f"/api/patients/{patient_b_id}/consent", json={
                "consent_type": "retinal_screening",
                "consent_status": "granted",
                "capture_method": "direct_clinical_intake"
            })
            assert hack_consent_post.status_code == 404

            # 11. User A listing NEVER shows Patient B
            list_a = await client_a.get("/api/patients")
            assert not any(p["id"] == patient_b_id for p in list_a.json()["items"])
            assert all(p["owner_user_id"] == user_a["id"] for p in list_a.json()["items"])

            # 12. User A searching for "Beta" returns 0 results
            search_a = await client_a.get("/api/patients?query=Beta")
            assert search_a.json()["total"] == 0
            assert len(search_a.json()["items"]) == 0

            # 13. Client cannot spoof ownership by injecting owner_user_id into request body
            spoof_res = await client_a.post("/api/patients", json={
                "full_name": "Spoof Attempt",
                "owner_user_id": user_b["id"]  # Attempt to assign to User B
            })
            assert spoof_res.status_code == 201
            assert spoof_res.json()["owner_user_id"] == user_a["id"]  # Derived strictly from server session!
