import uuid
from datetime import datetime, timedelta, timezone
import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from app.core.config import settings
from app.core.security import verify_password, hash_session_token
from app.models.user import User
from app.models.session import UserSession
from tests.conftest import TestAsyncSessionLocal


@pytest.mark.asyncio
async def test_successful_user_registration(client: AsyncClient):
    """1. Successful user registration returns 201 and sets HttpOnly cookie."""
    unique_email = f"user_{uuid.uuid4().hex[:8]}@retivue.org"
    payload = {
        "full_name": "Dr. Sarah Jenkins",
        "email": unique_email,
        "password": "SecurePassword2026!",
        "facility_name": "Retina Specialty Clinic",
        "registration_number": "MED-9941"
    }

    res = await client.post("/api/auth/register", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["success"] is True
    assert data["user"]["email"] == unique_email
    assert data["user"]["full_name"] == "Dr. Sarah Jenkins"
    assert data["user"]["facility_name"] == "Retina Specialty Clinic"
    # Ensure password and hash are NOT returned
    assert "password" not in data["user"]
    assert "password_hash" not in data["user"]
    # Ensure HttpOnly session cookie was issued
    assert settings.SESSION_COOKIE_NAME in res.cookies


@pytest.mark.asyncio
async def test_duplicate_email_rejection(client: AsyncClient):
    """2. Duplicate registration with same email returns 409 Conflict."""
    email = f"dup_{uuid.uuid4().hex[:8]}@retivue.org"
    payload = {
        "full_name": "First User",
        "email": email,
        "password": "Password123!"
    }
    res1 = await client.post("/api/auth/register", json=payload)
    assert res1.status_code == 201

    res2 = await client.post("/api/auth/register", json=payload)
    assert res2.status_code == 409
    assert "already exists" in res2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_email_normalization(client: AsyncClient):
    """3. Email normalization rejects duplicate with varied casing and whitespace."""
    base = f"norm_{uuid.uuid4().hex[:8]}"
    email_variant1 = f"  {base}@RETIVUE.ORG  "
    email_variant2 = f"{base.upper()}@retivue.org"

    res1 = await client.post("/api/auth/register", json={
        "full_name": "Normalized User",
        "email": email_variant1,
        "password": "Password123!"
    })
    assert res1.status_code == 201

    # Second registration with uppercase should be detected as duplicate
    res2 = await client.post("/api/auth/register", json={
        "full_name": "Duplicate User",
        "email": email_variant2,
        "password": "Password123!"
    })
    assert res2.status_code == 409


@pytest.mark.asyncio
async def test_password_stored_as_argon2id_hash(client: AsyncClient):
    """4 & 5. Password is never plaintext and verified as Argon2id hash in PostgreSQL."""
    email = f"argon_{uuid.uuid4().hex[:8]}@retivue.org"
    raw_password = "StrictlySecretArgon2id!"

    res = await client.post("/api/auth/register", json={
        "full_name": "Argon Tester",
        "email": email,
        "password": raw_password
    })
    assert res.status_code == 201
    user_id = res.json()["user"]["id"]

    # Inspect PostgreSQL directly
    async with TestAsyncSessionLocal() as session:
        stmt = select(User).where(User.id == user_id)
        user = (await session.execute(stmt)).scalar_one()
        assert user.password_hash != raw_password
        assert user.password_hash.startswith("$argon2id$")
        assert verify_password(raw_password, user.password_hash) is True


@pytest.mark.asyncio
async def test_successful_login(client: AsyncClient):
    """6. Successful login with correct credentials returns 200 and sets session cookie."""
    email = f"login_{uuid.uuid4().hex[:8]}@retivue.org"
    password = "CorrectPassword2026!"

    # Register first
    await client.post("/api/auth/register", json={
        "full_name": "Login Tester",
        "email": email,
        "password": password
    })

    # Clear cookies to simulate fresh client
    client.cookies.clear()

    # Login
    res = await client.post("/api/auth/login", json={
        "email": email,
        "password": password
    })
    assert res.status_code == 200
    assert res.json()["success"] is True
    assert settings.SESSION_COOKIE_NAME in res.cookies


@pytest.mark.asyncio
async def test_invalid_password_rejection(client: AsyncClient):
    """7. Invalid password returns generic 401 Unauthorized."""
    email = f"badpwd_{uuid.uuid4().hex[:8]}@retivue.org"
    await client.post("/api/auth/register", json={
        "full_name": "Security User",
        "email": email,
        "password": "ValidPassword123!"
    })

    client.cookies.clear()
    res = await client.post("/api/auth/login", json={
        "email": email,
        "password": "WrongPassword999!"
    })
    assert res.status_code == 401
    assert "invalid email or password" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_unknown_email_rejection(client: AsyncClient):
    """8. Unknown email returns generic 401 Unauthorized without leaking account existence."""
    res = await client.post("/api/auth/login", json={
        "email": "nonexistent_991823@retivue.org",
        "password": "AnyPassword123!"
    })
    assert res.status_code == 401
    assert "invalid email or password" in res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_session_creation_and_hash_storage(client: AsyncClient):
    """9 & 10. Session token is stored strictly as SHA-256 hash in PostgreSQL."""
    email = f"sess_{uuid.uuid4().hex[:8]}@retivue.org"
    res = await client.post("/api/auth/register", json={
        "full_name": "Session Tester",
        "email": email,
        "password": "Password123!"
    })
    assert res.status_code == 201
    user_id = res.json()["user"]["id"]
    raw_cookie_token = res.cookies.get(settings.SESSION_COOKIE_NAME)
    assert raw_cookie_token is not None

    expected_hash = hash_session_token(raw_cookie_token)

    async with TestAsyncSessionLocal() as session:
        stmt = select(UserSession).where(UserSession.user_id == user_id)
        db_session = (await session.execute(stmt)).scalars().first()
        assert db_session is not None
        assert db_session.token_hash == expected_hash
        assert db_session.token_hash != raw_cookie_token  # Raw token NEVER in DB


@pytest.mark.asyncio
async def test_get_me_with_and_without_session(client: AsyncClient):
    """11 & 12. GET /api/auth/me returns profile when session valid, 401 when missing."""
    client.cookies.clear()

    # Without session -> 401
    res_unauth = await client.get("/api/auth/me")
    assert res_unauth.status_code == 401

    # Register and get session
    email = f"me_{uuid.uuid4().hex[:8]}@retivue.org"
    reg = await client.post("/api/auth/register", json={
        "full_name": "Dr. Verified User",
        "email": email,
        "password": "Password123!"
    })
    assert reg.status_code == 201

    # With session -> 200
    res_auth = await client.get("/api/auth/me")
    assert res_auth.status_code == 200
    assert res_auth.json()["email"] == email
    assert res_auth.json()["full_name"] == "Dr. Verified User"


@pytest.mark.asyncio
async def test_session_expiry_rejection(client: AsyncClient):
    """14. Expired sessions are rejected with 401."""
    email = f"exp_{uuid.uuid4().hex[:8]}@retivue.org"
    reg = await client.post("/api/auth/register", json={
        "full_name": "Expiry Tester",
        "email": email,
        "password": "Password123!"
    })
    assert reg.status_code == 201
    user_id = reg.json()["user"]["id"]

    # Manually expire the session in PostgreSQL
    async with TestAsyncSessionLocal() as session:
        stmt = select(UserSession).where(UserSession.user_id == user_id)
        db_sess = (await session.execute(stmt)).scalars().first()
        db_sess.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        await session.commit()

    # Now request /api/auth/me -> should be 401 expired
    res = await client.get("/api/auth/me")
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_logout_revocation_and_reuse_rejection(client: AsyncClient):
    """15 & 16. Logout revokes session in DB; reuse of revoked session is rejected."""
    email = f"logout_{uuid.uuid4().hex[:8]}@retivue.org"
    reg = await client.post("/api/auth/register", json={
        "full_name": "Logout Tester",
        "email": email,
        "password": "Password123!"
    })
    assert reg.status_code == 201
    raw_token = reg.cookies.get(settings.SESSION_COOKIE_NAME)

    # Logout
    logout_res = await client.post("/api/auth/logout")
    assert logout_res.status_code == 200
    assert logout_res.json()["success"] is True

    # Attempt to use the old raw_token manually
    client.cookies.set(settings.SESSION_COOKIE_NAME, raw_token)
    res_reuse = await client.get("/api/auth/me")
    assert res_reuse.status_code == 401


@pytest.mark.asyncio
async def test_inactive_account_rejection(client: AsyncClient):
    """17. Deactivated user accounts are rejected on both login and authenticated calls."""
    email = f"inact_{uuid.uuid4().hex[:8]}@retivue.org"
    password = "Password123!"
    reg = await client.post("/api/auth/register", json={
        "full_name": "Inactive Tester",
        "email": email,
        "password": password
    })
    assert reg.status_code == 201
    user_id = reg.json()["user"]["id"]

    # Deactivate account in PostgreSQL
    async with TestAsyncSessionLocal() as session:
        stmt = select(User).where(User.id == user_id)
        user = (await session.execute(stmt)).scalar_one()
        user.is_active = False
        await session.commit()

    # Authenticated call with active cookie should now be 403 Forbidden
    res_me = await client.get("/api/auth/me")
    assert res_me.status_code == 403

    # Subsequent login should also fail
    client.cookies.clear()
    res_login = await client.post("/api/auth/login", json={
        "email": email,
        "password": password
    })
    assert res_login.status_code == 401


@pytest.mark.asyncio
async def test_csrf_token_endpoint_and_validation(client: AsyncClient):
    """18. GET /api/auth/csrf issues token; mismatch on state-changing request is rejected."""
    csrf_res = await client.get("/api/auth/csrf")
    assert csrf_res.status_code == 200
    token = csrf_res.json()["csrf_token"]
    assert len(token) >= 32

    # Provide a mismatched CSRF header while CSRF cookie is active
    headers = {
        settings.CSRF_HEADER_NAME: "invalid-csrf-token-12345",
        "Origin": "http://localhost:3000"
    }
    bad_post = await client.post("/api/auth/login", json={
        "email": "test@retivue.org",
        "password": "Password123!"
    }, headers=headers)
    assert bad_post.status_code == 403
    assert "csrf" in bad_post.json()["detail"].lower()


@pytest.mark.asyncio
async def test_profile_update_authorization(client: AsyncClient):
    """20. Authenticated user can update full_name, facility, registration number."""
    client.cookies.clear()
    email = f"prof_{uuid.uuid4().hex[:8]}@retivue.org"
    reg = await client.post("/api/auth/register", json={
        "full_name": "Original Name",
        "email": email,
        "password": "Password123!"
    })
    assert reg.status_code == 201

    # Update profile
    patch_res = await client.patch("/api/auth/me", json={
        "full_name": "Updated Clinical Operator",
        "facility_name": "Apex Eye Institute",
        "registration_number": "REG-8822"
    })
    assert patch_res.status_code == 200
    updated_data = patch_res.json()
    assert updated_data["full_name"] == "Updated Clinical Operator"
    assert updated_data["facility_name"] == "Apex Eye Institute"
    assert updated_data["registration_number"] == "REG-8822"

