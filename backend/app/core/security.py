import hashlib
import hmac
import secrets
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from app.core.config import settings

# Argon2id password hasher with recommended parameters
ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,  # 64 MB
    parallelism=1,
    hash_len=32
)

MAX_PASSWORD_LENGTH = 128
MIN_PASSWORD_LENGTH = 8


def normalize_email(email: str) -> str:
    """Consistently normalizes email addresses by stripping whitespace and lowercasing."""
    if not email:
        return ""
    return email.strip().lower()


def hash_password(password: str) -> str:
    """Hashes plain password using Argon2id with length validation."""
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters long.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password exceeds maximum allowed length of {MAX_PASSWORD_LENGTH} characters.")
    return ph.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies plain password against Argon2id hash without exposing internals."""
    if not plain_password or not hashed_password:
        return False
    if len(plain_password) > MAX_PASSWORD_LENGTH:
        return False
    try:
        return ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def generate_session_token() -> str:
    """Generates a cryptographically secure random session token (32 bytes urlsafe)."""
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    """Computes SHA-256 hash of the session token for secure database storage."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_csrf_token() -> str:
    """Generates a cryptographically secure random CSRF token."""
    return secrets.token_hex(32)


def verify_csrf_token(client_token: str, expected_token: str) -> bool:
    """Constant-time comparison of CSRF tokens to prevent timing attacks."""
    if not client_token or not expected_token:
        return False
    return hmac.compare_digest(client_token.strip(), expected_token.strip())
