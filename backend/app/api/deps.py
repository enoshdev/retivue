from typing import Optional
from fastapi import Request, HTTPException, status, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config import settings
from app.core.security import hash_session_token, verify_csrf_token
from app.database.session import get_db
from app.repositories.session_repository import SessionRepository
from app.models.user import User
from app.models.session import UserSession
from app.core.logging import logger


async def get_current_session(
    request: Request,
    db: AsyncSession = Depends(get_db)
) -> UserSession:
    """
    Extracts session token from HttpOnly cookie, verifies token hash against PostgreSQL,
    and returns the active UserSession.
    """
    raw_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication session required."
        )

    token_hash = hash_session_token(raw_token)
    session = await SessionRepository.get_active_session_by_token_hash(db, token_hash)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired or been revoked. Please log in again."
        )

    # Touch session to track last active usage
    await SessionRepository.touch(db, session)
    return session


async def get_current_user(
    session: UserSession = Depends(get_current_session)
) -> User:
    """
    Returns the authenticated User derived strictly from the server-verified session.
    Never trusts client-supplied identifiers.
    """
    user = session.user
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account associated with session not found."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated. Please contact support."
        )

    return user


async def require_csrf(request: Request) -> None:
    """
    Enforces CSRF protection on state-changing HTTP requests.
    Validates origin header and matches X-CSRF-Token header with the retivue_csrf cookie.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return

    # Validate Origin header if present
    origin = request.headers.get("origin")
    if origin and origin not in settings.BACKEND_CORS_ORIGINS:
        logger.warning(f"CSRF protection: rejected unauthorized origin '{origin}'")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Request origin not permitted."
        )

    # Double-submit cookie verification: mandatory whenever a session cookie is present
    # or a CSRF cookie was issued.
    session_cookie = request.cookies.get(settings.SESSION_COOKIE_NAME)
    csrf_cookie = request.cookies.get(settings.CSRF_COOKIE_NAME)
    csrf_header = request.headers.get(settings.CSRF_HEADER_NAME) or request.headers.get("x-csrf-token")

    if session_cookie or csrf_cookie:
        if not csrf_cookie or not csrf_header or not verify_csrf_token(csrf_header, csrf_cookie):
            logger.warning("CSRF protection: missing or mismatched CSRF cookie/header.")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="CSRF validation failed."
            )
