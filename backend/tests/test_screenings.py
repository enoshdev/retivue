import hashlib
import io
import os
import uuid
import zlib
import struct
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import AsyncClient, ASGITransport
from PIL import Image
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.main import app
from app.models.screening import Screening
from app.models.screening_image import ScreeningImage
from app.storage.base import StorageError
from tests.conftest import CSRFAutoClient, TestAsyncSessionLocal


def _make_jpeg_bytes(width: int = 256, height: int = 256, color=(140, 60, 40)) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def _make_png_bytes(width: int = 256, height: int = 256, color=(30, 110, 70)) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", (width, height), color=color)
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_decompression_bomb_png(width: int = 8000, height: int = 6000) -> bytes:
    """
    Construct a genuine minimal valid PNG header+IDAT with 48,000,000 pixels
    (> MAX_IMAGE_PIXELS=40,000,000) in only a few KB using zlib solid scanlines.
    """
    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    # Minimal compressed 1-row sample (or valid compressed buffer for small bomb test)
    # Using Pillow or zlib: actually building full zeroed scanlines for 8000x6000x3 compresses well
    row = b"\x00" + (b"\x00" * (width * 3))
    raw_scanlines = row * height
    compressed = zlib.compress(raw_scanlines, level=1)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", compressed)
        + chunk(b"IEND", b"")
    )


async def _register_clinician(client: AsyncClient, tag: str) -> dict:
    csrf_res = await client.get("/api/auth/csrf")
    assert csrf_res.status_code == 200
    csrf_token = csrf_res.json()["csrf_token"]

    res = await client.post(
        "/api/auth/register",
        json={
            "full_name": f"Dr. {tag}",
            "email": f"{tag}.{uuid.uuid4().hex[:6]}@retivue-clinic.org",
            "password": "StrongPassword2026!",
            "facility_name": "Retina Screening Unit",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert res.status_code == 201
    return res.json()["user"]


async def _create_patient(
    client: AsyncClient,
    name: str = "Lakshmi Devi",
    consent_status: str = "granted",
    with_consent: bool = True,
) -> dict:
    payload: dict = {
        "full_name": name,
        "patient_code": f"MRN-{uuid.uuid4().hex[:6].upper()}",
        "sex": "female",
        "diabetes_type": "Type 2",
        "diabetes_duration_years": 7,
        "recent_hba1c": "7.5%",
    }
    if with_consent:
        payload["initial_consent"] = {
            "consent_type": "retinal_screening",
            "consent_status": consent_status,
            "capture_method": "digital_acknowledgement",
        }
    res = await client.post("/api/patients", json=payload)
    assert res.status_code == 201
    return res.json()


# ==============================================================================
# 1. AUTHENTICATION, SCREENING LIFECYCLE & DATABASE CONSTRAINTS
# ==============================================================================


@pytest.mark.asyncio
async def test_unauthenticated_screening_endpoints_rejected(client: AsyncClient):
    """Unauthenticated access to screenings and retinal images must return 401."""
    assert (await client.get("/api/screenings")).status_code == 401
    assert (await client.post("/api/screenings", json={"patient_id": str(uuid.uuid4())})).status_code == 401
    fake_id = str(uuid.uuid4())
    assert (await client.get(f"/api/screenings/{fake_id}")).status_code == 401
    assert (await client.get(f"/api/screenings/{fake_id}/images/OD")).status_code == 401
    assert (await client.post(f"/api/screenings/{fake_id}/submit")).status_code == 401


@pytest.mark.asyncio
async def test_create_list_retrieve_screening_workflow(client: AsyncClient):
    """Verify screening creation, unique reference, ownership derivation, list filtering, and retrieval."""
    user = await _register_clinician(client, "workflow")
    patient = await _create_patient(client, "Workflow Patient")

    # Spoofed owner_user_id in request must be ignored
    create_res = await client.post(
        "/api/screenings",
        json={
            "patient_id": patient["id"],
            "camera_model": "Topcon TRC-NW400",
            "clinical_notes": "Baseline annual DR surveillance",
            "owner_user_id": str(uuid.uuid4()),
        },
    )
    assert create_res.status_code == 201
    screening = create_res.json()
    assert screening["owner_user_id"] == user["id"]
    assert screening["patient_id"] == patient["id"]
    assert screening["screening_reference"].startswith("SCR-")
    assert screening["status"] == "awaiting_images"
    assert screening["has_od_image"] is False
    assert screening["has_os_image"] is False
    assert screening["is_bilateral_complete"] is False

    # Retrieve by ID
    get_res = await client.get(f"/api/screenings/{screening['id']}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == screening["id"]
    assert get_res.json()["patient"]["full_name"] == "Workflow Patient"

    # List filtered by patient_id & status
    list_res = await client.get(f"/api/screenings?patient_id={patient['id']}&status=awaiting_images")
    assert list_res.status_code == 200
    data = list_res.json()
    assert data["total"] == 1
    assert data["items"][0]["id"] == screening["id"]

    # Invalid screening ID handled safely with 404
    missing_res = await client.get(f"/api/screenings/{uuid.uuid4()}")
    assert missing_res.status_code == 404


@pytest.mark.asyncio
async def test_db_unique_current_eye_constraints(client: AsyncClient):
    """Verify PostgreSQL partial unique indexes reject duplicate current OD or OS images."""
    user = await _register_clinician(client, "dbconstraint")
    patient = await _create_patient(client, "Constraint Subject")
    create_res = await client.post("/api/screenings", json={"patient_id": patient["id"]})
    screening_id = create_res.json()["id"]

    # Insert first current OD directly, then attempt duplicate current OD -> IntegrityError
    async with TestAsyncSessionLocal() as session:
        img1 = ScreeningImage(
            id=str(uuid.uuid4()),
            screening_id=screening_id,
            owner_user_id=user["id"],
            eye="OD",
            storage_key=f"screenings/{screening_id}/od/test1_{uuid.uuid4().hex}.jpg",
            detected_media_type="image/jpeg",
            file_extension=".jpg",
            file_size_bytes=1024,
            image_width=256,
            image_height=256,
            sha256_checksum=hashlib.sha256(b"a").hexdigest(),
            is_current=True,
        )
        session.add(img1)
        await session.commit()

        dup_od = ScreeningImage(
            id=str(uuid.uuid4()),
            screening_id=screening_id,
            owner_user_id=user["id"],
            eye="OD",
            storage_key=f"screenings/{screening_id}/od/test2_{uuid.uuid4().hex}.jpg",
            detected_media_type="image/jpeg",
            file_extension=".jpg",
            file_size_bytes=1024,
            image_width=256,
            image_height=256,
            sha256_checksum=hashlib.sha256(b"b").hexdigest(),
            is_current=True,
        )
        session.add(dup_od)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()

        # Verify same partial unique index blocks duplicate current OS
        os1 = ScreeningImage(
            id=str(uuid.uuid4()),
            screening_id=screening_id,
            owner_user_id=user["id"],
            eye="OS",
            storage_key=f"screenings/{screening_id}/os/test1_{uuid.uuid4().hex}.png",
            detected_media_type="image/png",
            file_extension=".png",
            file_size_bytes=1024,
            image_width=256,
            image_height=256,
            sha256_checksum=hashlib.sha256(b"c").hexdigest(),
            is_current=True,
        )
        session.add(os1)
        await session.commit()

        dup_os = ScreeningImage(
            id=str(uuid.uuid4()),
            screening_id=screening_id,
            owner_user_id=user["id"],
            eye="OS",
            storage_key=f"screenings/{screening_id}/os/test2_{uuid.uuid4().hex}.png",
            detected_media_type="image/png",
            file_extension=".png",
            file_size_bytes=1024,
            image_width=256,
            image_height=256,
            sha256_checksum=hashlib.sha256(b"d").hexdigest(),
            is_current=True,
        )
        session.add(dup_os)
        with pytest.raises(IntegrityError):
            await session.commit()
        await session.rollback()


# ==============================================================================
# 2. IMAGE UPLOAD, FORMAT VALIDATION, PRESERVATION & ATOMIC COMPENSATION
# ==============================================================================


@pytest.mark.asyncio
async def test_valid_jpeg_and_png_upload_preservation_and_retrieval(
    client: AsyncClient,
    test_storage,
):
    """
    Verify valid JPEG & PNG upload, byte-for-byte original preservation, SHA-256 verification,
    private storage outside public dirs, no storage_key leakage, bilateral status transitions,
    and authorized image streaming.
    """
    await _register_clinician(client, "imgvalid")
    patient = await _create_patient(client, "Bilateral Subject")
    create_res = await client.post("/api/screenings", json={"patient_id": patient["id"]})
    screening_id = create_res.json()["id"]

    raw_od_jpeg = _make_jpeg_bytes(320, 240, color=(180, 75, 45))
    raw_os_png = _make_png_bytes(400, 300, color=(90, 120, 60))
    od_sha = hashlib.sha256(raw_od_jpeg).hexdigest()
    os_sha = hashlib.sha256(raw_os_png).hexdigest()

    # Upload OD (JPEG) -> status must transition to images_incomplete
    od_res = await client.post(
        f"/api/screenings/{screening_id}/images/OD",
        files={"file": ("patient_od_photo.jpg", raw_od_jpeg, "image/jpeg")},
    )
    assert od_res.status_code == 201
    od_data = od_res.json()
    assert od_data["eye"] == "OD"
    assert od_data["detected_media_type"] == "image/jpeg"
    assert od_data["image_width"] == 320
    assert od_data["image_height"] == 240
    assert od_data["file_size_bytes"] == len(raw_od_jpeg)
    assert od_data["sha256_checksum"] == od_sha
    assert od_data["screening_status"] == "images_incomplete"
    assert od_data["is_bilateral_complete"] is False
    # Never expose internal storage_key or path
    assert "storage_key" not in od_data
    assert str(test_storage.root_dir) not in od_res.text

    # Single-eye screening CANNOT be submitted yet
    incomplete_submit = await client.post(f"/api/screenings/{screening_id}/submit")
    assert incomplete_submit.status_code == 422

    # Upload OS (PNG) -> status transitions to draft (bilateral complete, pending submit)
    os_res = await client.post(
        f"/api/screenings/{screening_id}/images/OS",
        files={"file": ("patient_os_photo.png", raw_os_png, "image/png")},
    )
    assert os_res.status_code == 201
    os_data = os_res.json()
    assert os_data["detected_media_type"] == "image/png"
    assert os_data["sha256_checksum"] == os_sha
    assert os_data["screening_status"] == "draft"
    assert os_data["is_bilateral_complete"] is True

    # Verify private storage is outside workspace public/ directory and original bytes are unaltered
    project_public = Path(__file__).resolve().parent.parent.parent / "public"
    assert not str(test_storage.root_dir).startswith(str(project_public))

    async with TestAsyncSessionLocal() as session:
        imgs = (
            await session.execute(
                select(ScreeningImage).where(ScreeningImage.screening_id == screening_id)
            )
        ).scalars().all()
        assert len(imgs) == 2
        for img in imgs:
            disk_bytes = await test_storage.read_bytes(img.storage_key)
            if img.eye == "OD":
                assert disk_bytes == raw_od_jpeg
            else:
                assert disk_bytes == raw_os_png

    # Retrieve streamed images via authenticated API
    get_od = await client.get(f"/api/screenings/{screening_id}/images/OD")
    assert get_od.status_code == 200
    assert get_od.headers["content-type"] == "image/jpeg"
    assert "private" in get_od.headers["cache-control"]
    assert get_od.headers["x-content-type-options"] == "nosniff"
    assert get_od.content == raw_od_jpeg

    get_os = await client.get(f"/api/screenings/{screening_id}/images/OS")
    assert get_os.status_code == 200
    assert get_os.headers["content-type"] == "image/png"
    assert get_os.content == raw_os_png

    # Submit screening for quality assessment
    submit_res = await client.post(f"/api/screenings/{screening_id}/submit")
    assert submit_res.status_code == 200
    submitted = submit_res.json()
    assert submitted["status"] == "ready_for_quality_assessment"
    assert submitted["submitted_at"] is not None


@pytest.mark.asyncio
async def test_upload_validation_rejects_malformed_and_disallowed_files(client: AsyncClient, monkeypatch):
    """Verify validation rejects empty, oversized, bad MIME, bad magic bytes, mismatched ext, corrupt, small dims, bomb, executables."""
    await _register_clinician(client, "validator")
    patient = await _create_patient(client, "Validation Patient")
    create_res = await client.post("/api/screenings", json={"patient_id": patient["id"]})
    sid = create_res.json()["id"]
    url_od = f"/api/screenings/{sid}/images/OD"

    # 1. Invalid eye parameter
    bad_eye = await client.post(
        f"/api/screenings/{sid}/images/LEFT",
        files={"file": ("eye.jpg", _make_jpeg_bytes(), "image/jpeg")},
    )
    assert bad_eye.status_code == 422

    # 2. Empty file
    empty_res = await client.post(url_od, files={"file": ("empty.jpg", b"", "image/jpeg")})
    assert empty_res.status_code == 422

    # 3. Invalid MIME type
    bad_mime = await client.post(url_od, files={"file": ("doc.pdf", b"%PDF-1.4\n...", "application/pdf")})
    assert bad_mime.status_code == 415

    # 4. Executable PE binary disguised as .jpg & image/jpeg
    exe_res = await client.post(url_od, files={"file": ("evil.jpg", b"MZ\x90\x00" + b"A" * 500, "image/jpeg")})
    assert exe_res.status_code == 415

    # 5. SVG XSS payload disguised with .png
    svg_res = await client.post(
        url_od,
        files={"file": ("xss.png", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>', "image/png")},
    )
    assert svg_res.status_code == 415

    # 6. Incorrect magic signature claiming image/jpeg
    fake_sig = await client.post(url_od, files={"file": ("fake.jpg", b"NOT_AN_IMAGE_AT_ALL_12345", "image/jpeg")})
    assert fake_sig.status_code == 415

    # 7. Extension mismatch (valid PNG bytes uploaded with .jpg extension and image/png or image/jpeg)
    valid_png = _make_png_bytes()
    ext_mismatch = await client.post(url_od, files={"file": ("wrong.jpg", valid_png, "image/png")})
    assert ext_mismatch.status_code == 422

    # 8. Truncated / corrupt JPEG
    valid_jpeg = _make_jpeg_bytes(256, 256)
    truncated_jpeg = valid_jpeg[: len(valid_jpeg) // 3]
    corrupt_res = await client.post(url_od, files={"file": ("corrupt.jpg", truncated_jpeg, "image/jpeg")})
    assert corrupt_res.status_code == 422

    # 9. Invalid dimensions (below MIN_IMAGE_WIDTH x MIN_IMAGE_HEIGHT = 128x128)
    tiny_png = _make_png_bytes(32, 32)
    tiny_res = await client.post(url_od, files={"file": ("tiny.png", tiny_png, "image/png")})
    assert tiny_res.status_code == 422

    # 10. Decompression bomb protection (> MAX_IMAGE_PIXELS)
    bomb_png = _make_decompression_bomb_png(8000, 6000)  # 48 MP > 40 MP threshold
    bomb_res = await client.post(url_od, files={"file": ("bomb.png", bomb_png, "image/png")})
    assert bomb_res.status_code == 422

    # 11. Oversized file limit check (temporarily tighten limit to 10 KB for fast test)
    monkeypatch.setattr(settings, "MAX_UPLOAD_SIZE_BYTES", 10 * 1024)
    large_png = _make_png_bytes(600, 600)
    # Force noisy bytes so PNG exceeds 10 KB
    noisy_img = Image.frombytes("RGB", (400, 400), os.urandom(400 * 400 * 3))
    noisy_buf = io.BytesIO()
    noisy_img.save(noisy_buf, format="PNG")
    oversized_res = await client.post(url_od, files={"file": ("huge.png", noisy_buf.getvalue(), "image/png")})
    assert oversized_res.status_code == 413


@pytest.mark.asyncio
async def test_image_replacement_preserves_history_and_originals(client: AsyncClient, test_storage):
    """Verify replacing an eye image keeps previous original file and creates auditable replacement history."""
    await _register_clinician(client, "replacer")
    patient = await _create_patient(client, "Replacement Patient")
    sid = (await client.post("/api/screenings", json={"patient_id": patient["id"]})).json()["id"]

    bytes_v1 = _make_jpeg_bytes(256, 256, color=(150, 50, 50))
    bytes_v2 = _make_png_bytes(300, 300, color=(50, 150, 50))

    # First upload
    up1 = await client.post(
        f"/api/screenings/{sid}/images/OD",
        files={"file": ("od_v1.jpg", bytes_v1, "image/jpeg")},
    )
    assert up1.status_code == 201
    v1_id = up1.json()["id"]

    # Double POST without replace must return 409 Conflict
    dup_post = await client.post(
        f"/api/screenings/{sid}/images/OD",
        files={"file": ("od_v2.png", bytes_v2, "image/png")},
    )
    assert dup_post.status_code == 409

    # Controlled replacement succeeds
    rep_res = await client.post(
        f"/api/screenings/{sid}/images/OD/replace",
        files={"file": ("od_v2.png", bytes_v2, "image/png")},
    )
    assert rep_res.status_code == 200
    v2_data = rep_res.json()
    assert v2_data["id"] != v1_id
    assert v2_data["is_current"] is True
    assert v2_data["sha256_checksum"] == hashlib.sha256(bytes_v2).hexdigest()

    # GET returns only current image (v2)
    curr_stream = await client.get(f"/api/screenings/{sid}/images/OD")
    assert curr_stream.status_code == 200
    assert curr_stream.content == bytes_v2

    # History endpoint returns both records with audit fields
    hist_res = await client.get(f"/api/screenings/{sid}/images/OD/history")
    assert hist_res.status_code == 200
    hist = hist_res.json()
    assert len(hist) == 2
    assert hist[0]["id"] == v2_data["id"]
    assert hist[0]["is_current"] is True
    assert hist[1]["id"] == v1_id
    assert hist[1]["is_current"] is False
    assert hist[1]["upload_status"] == "replaced"
    assert hist[1]["replaced_at"] is not None

    # Verify BOTH original files still exist unmodified in private storage
    async with TestAsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(ScreeningImage).where(
                    ScreeningImage.screening_id == sid,
                    ScreeningImage.eye == "OD",
                )
            )
        ).scalars().all()
        assert len(rows) == 2
        for r in rows:
            stored = await test_storage.read_bytes(r.storage_key)
            if r.id == v1_id:
                assert stored == bytes_v1
            else:
                assert stored == bytes_v2


@pytest.mark.asyncio
async def test_failure_compensation_storage_and_database(client: AsyncClient, test_storage):
    """
    Verify:
    1) Storage failure does NOT create a false DB record.
    2) Database failure deletes newly written file so no untracked permanent file remains.
    """
    await _register_clinician(client, "failcomp")
    patient = await _create_patient(client, "Compensation Patient")
    sid = (await client.post("/api/screenings", json={"patient_id": patient["id"]})).json()["id"]
    img_bytes = _make_jpeg_bytes(256, 256)

    # Case 1: Storage failure
    with patch.object(test_storage, "save_bytes", side_effect=StorageError("Simulated disk failure")):
        fail_res = await client.post(
            f"/api/screenings/{sid}/images/OD",
            files={"file": ("od.jpg", img_bytes, "image/jpeg")},
        )
        assert fail_res.status_code == 500

    async with TestAsyncSessionLocal() as session:
        count_od = (
            await session.execute(
                select(ScreeningImage).where(ScreeningImage.screening_id == sid)
            )
        ).scalars().all()
        assert len(count_od) == 0

    # Case 2: Database write failure -> newly written storage file MUST be cleaned up
    screening_dir = test_storage.root_dir / "screenings" / sid
    with patch(
        "app.services.screening_service.ScreeningRepository.save_image_record",
        side_effect=RuntimeError("Simulated DB commit failure"),
    ):
        db_fail_res = await client.post(
            f"/api/screenings/{sid}/images/OS",
            files={"file": ("os.jpg", img_bytes, "image/jpeg")},
        )
        assert db_fail_res.status_code == 500

    # Ensure zero files exist inside screening_dir/os
    os_dir = screening_dir / "os"
    if os_dir.exists():
        assert list(os_dir.iterdir()) == []


# ==============================================================================
# 3. CONSENT GATE & CRITICAL CROSS-ACCOUNT SECURITY ISOLATION
# ==============================================================================


@pytest.mark.asyncio
async def test_missing_pending_and_revoked_consent_blocks_submission(client: AsyncClient):
    """Verify missing, pending, and revoked consent blocks quality assessment submission."""
    await _register_clinician(client, "consentgate")

    # Patient with NO consent record
    no_consent_patient = await _create_patient(client, "No Consent Subject", with_consent=False)
    sid1 = (await client.post("/api/screenings", json={"patient_id": no_consent_patient["id"]})).json()["id"]
    await client.post(f"/api/screenings/{sid1}/images/OD", files={"file": ("od.jpg", _make_jpeg_bytes(), "image/jpeg")})
    await client.post(f"/api/screenings/{sid1}/images/OS", files={"file": ("os.png", _make_png_bytes(), "image/png")})

    sub1 = await client.post(f"/api/screenings/{sid1}/submit")
    assert sub1.status_code == 403
    assert "consent" in sub1.json()["detail"].lower()

    # Patient with granted consent -> revoked before submission
    rev_patient = await _create_patient(client, "Revoked Consent Subject", consent_status="granted")
    sid2 = (await client.post("/api/screenings", json={"patient_id": rev_patient["id"]})).json()["id"]
    await client.post(f"/api/screenings/{sid2}/images/OD", files={"file": ("od.jpg", _make_jpeg_bytes(), "image/jpeg")})
    await client.post(f"/api/screenings/{sid2}/images/OS", files={"file": ("os.png", _make_png_bytes(), "image/png")})

    revoke_res = await client.post(
        f"/api/patients/{rev_patient['id']}/consent/revoke",
        json={"notes": "Patient withdrew permission"},
    )
    assert revoke_res.status_code == 200

    sub2 = await client.post(f"/api/screenings/{sid2}/submit")
    assert sub2.status_code == 403
    assert "revoked" in sub2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_cross_account_screening_and_image_isolation():
    """
    CRITICAL SECURITY TEST:
    Verify User A and User B have strictly isolated screenings and retinal images across every endpoint.
    """
    transport = ASGITransport(app=app)
    async with CSRFAutoClient(transport=transport, base_url="http://test") as client_a:
        async with CSRFAutoClient(transport=transport, base_url="http://test") as client_b:
            await _register_clinician(client_a, "tenantA")
            await _register_clinician(client_b, "tenantB")

            patient_a = await _create_patient(client_a, "Patient A")
            patient_b = await _create_patient(client_b, "Patient B")

            scr_a = (await client_a.post("/api/screenings", json={"patient_id": patient_a["id"]})).json()
            scr_b = (await client_b.post("/api/screenings", json={"patient_id": patient_b["id"]})).json()

            # Upload bilateral images for User B
            await client_b.post(
                f"/api/screenings/{scr_b['id']}/images/OD",
                files={"file": ("b_od.jpg", _make_jpeg_bytes(), "image/jpeg")},
            )
            await client_b.post(
                f"/api/screenings/{scr_b['id']}/images/OS",
                files={"file": ("b_os.png", _make_png_bytes(), "image/png")},
            )

            # 1. User A cannot create screening using User B's patient
            cross_pat_res = await client_a.post("/api/screenings", json={"patient_id": patient_b["id"]})
            assert cross_pat_res.status_code == 404

            # 2. User A listing never includes User B's screening
            list_a = (await client_a.get("/api/screenings")).json()
            assert all(item["id"] != scr_b["id"] for item in list_a["items"])

            # 3. User A cannot retrieve User B's screening (even knowing exact UUID)
            assert (await client_a.get(f"/api/screenings/{scr_b['id']}")).status_code == 404

            # 4. User A cannot upload an image to User B's screening
            up_cross = await client_a.post(
                f"/api/screenings/{scr_b['id']}/images/OD",
                files={"file": ("hack.jpg", _make_jpeg_bytes(), "image/jpeg")},
            )
            assert up_cross.status_code == 404

            # 5. User A cannot retrieve User B's eye images
            assert (await client_a.get(f"/api/screenings/{scr_b['id']}/images/OD")).status_code == 404
            assert (await client_a.get(f"/api/screenings/{scr_b['id']}/images/OS")).status_code == 404

            # 6. User A cannot replace User B's eye image
            rep_cross = await client_a.post(
                f"/api/screenings/{scr_b['id']}/images/OD/replace",
                files={"file": ("hack_rep.jpg", _make_jpeg_bytes(), "image/jpeg")},
            )
            assert rep_cross.status_code == 404

            # 7. User A cannot inspect User B's image history
            assert (await client_a.get(f"/api/screenings/{scr_b['id']}/images/OD/history")).status_code == 404

            # 8. User A cannot submit User B's screening
            assert (await client_a.post(f"/api/screenings/{scr_b['id']}/submit")).status_code == 404

            # 9. Confirm User B's screening was completely unaffected
            verify_b = await client_b.get(f"/api/screenings/{scr_b['id']}")
            assert verify_b.status_code == 200
            assert verify_b.json()["status"] == "draft"
            assert verify_b.json()["is_bilateral_complete"] is True
            assert (await client_b.get(f"/api/screenings/{scr_a['id']}")).status_code == 404


@pytest.mark.asyncio
async def test_exif_metadata_detected_and_original_bytes_untouched(client: AsyncClient, test_storage):
    """Verify EXIF metadata is detected while original uploaded bytes remain 100% unmodified."""
    await _register_clinician(client, "exif")
    patient = await _create_patient(client, "EXIF Patient")
    sid = (await client.post("/api/screenings", json={"patient_id": patient["id"]})).json()["id"]

    buf = io.BytesIO()
    img = Image.new("RGB", (256, 256), color=(110, 80, 60))
    exif = img.getexif()
    exif[0x010E] = "Clinic Device Metadata Sample"
    img.save(buf, format="JPEG", exif=exif, quality=95)
    raw_with_exif = buf.getvalue()

    res = await client.post(
        f"/api/screenings/{sid}/images/OD",
        files={"file": ("exif_fundus.jpg", raw_with_exif, "image/jpeg")},
    )
    assert res.status_code == 201
    meta = res.json()
    assert meta["has_exif_metadata"] is True
    assert meta["sha256_checksum"] == hashlib.sha256(raw_with_exif).hexdigest()

    retrieved = await client.get(f"/api/screenings/{sid}/images/OD")
    assert retrieved.status_code == 200
    assert retrieved.content == raw_with_exif


@pytest.mark.asyncio
async def test_storage_path_traversal_and_s3_boundary(test_storage):
    """Verify local storage rejects traversal keys and S3 adapter fails cleanly when unconfigured."""
    from app.storage.base import StoragePathSecurityError, StorageConfigurationError
    from app.storage.s3 import S3CompatibleStorage

    for malicious_key in ("../escape.jpg", "/abs/path.jpg", "screenings/../../secret.png", "bad key spaces.jpg"):
        with pytest.raises(StoragePathSecurityError):
            await test_storage.save_bytes(malicious_key, b"data", "image/jpeg")
        with pytest.raises(StoragePathSecurityError):
            await test_storage.read_bytes(malicious_key)

    with pytest.raises(StorageConfigurationError):
        S3CompatibleStorage(bucket_name=None)
    s3_stub = S3CompatibleStorage(bucket_name="retivue-future-bucket")
    with pytest.raises(StorageConfigurationError):
        await s3_stub.save_bytes("screenings/1/od/a.jpg", b"data", "image/jpeg")
