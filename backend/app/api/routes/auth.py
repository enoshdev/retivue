from fastapi import APIRouter, Depends, Response, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.session import get_db
from app.schemas.auth import (
    UserRegisterRequest,
    UserLoginRequest,
    UserProfileUpdate,
    SafeUserResponse,
    AuthSuccessResponse,
    CSRFResponse
)
from app.services.auth_service import AuthService
from app.models.user import User
from app.models.session import UserSession
from app.api.deps import get_current_user, get_current_session, require_csrf
from app.core.config import settings
from app.core.security import generate_csrf_token

router = APIRouter(prefix="/auth", tags=["Authentication & Identity"])


def _set_auth_cookies(response: Response, raw_session_token: str, csrf_token: str) -> None:
    """Sets secure HttpOnly session cookie and client-readable CSRF token cookie."""
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_session_token,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path=settings.COOKIE_PATH
    )
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        httponly=False,  # Client-side JS reads this to supply X-CSRF-Token header
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path=settings.COOKIE_PATH
    )


@router.get(
    "/csrf",
    response_model=CSRFResponse,
    summary="Obtain CSRF Token",
    description="Provides a synchronizer CSRF token and sets the retivue_csrf cookie for state-changing requests."
)
async def get_csrf_token(response: Response):
    """Provides a fresh CSRF token."""
    csrf_token = generate_csrf_token()
    response.set_cookie(
        key=settings.CSRF_COOKIE_NAME,
        value=csrf_token,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path=settings.COOKIE_PATH
    )
    return CSRFResponse(csrf_token=csrf_token)


@router.post(
    "/register",
    response_model=AuthSuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Individual User Account",
    description="Creates a new user record with Argon2id password hash, initializes a persistent session, and sets HttpOnly cookie."
)
async def register(
    payload: UserRegisterRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf)
):
    """Registers a new user account."""
    user, raw_token = await AuthService.register_user(
        db=db,
        full_name=payload.full_name,
        email=payload.email,
        password=payload.password,
        facility_name=payload.facility_name,
        registration_number=payload.registration_number
    )

    csrf_token = request.cookies.get(settings.CSRF_COOKIE_NAME) or generate_csrf_token()
    _set_auth_cookies(response, raw_token, csrf_token)

    return AuthSuccessResponse(
        success=True,
        message="Account registered successfully. Welcome to RETIVUE.",
        user=SafeUserResponse.model_validate(user)
    )


@router.post(
    "/login",
    response_model=AuthSuccessResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description="Authenticates credentials against Argon2id hash, initializes a server-side session, and sets HttpOnly cookie."
)
async def login(
    payload: UserLoginRequest,
    response: Response,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf)
):
    """Authenticates credentials and establishes session."""
    user, raw_token = await AuthService.login_user(
        db=db,
        email=payload.email,
        password=payload.password
    )

    csrf_token = request.cookies.get(settings.CSRF_COOKIE_NAME) or generate_csrf_token()
    _set_auth_cookies(response, raw_token, csrf_token)

    return AuthSuccessResponse(
        success=True,
        message="Signed in successfully.",
        user=SafeUserResponse.model_validate(user)
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="User Logout",
    description="Revokes the persistent session in PostgreSQL and removes the HttpOnly session cookie."
)
async def logout(
    response: Response,
    session: UserSession = Depends(get_current_session),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf)
):
    """Revokes active session and clears auth cookies."""
    await AuthService.logout_session(db, session)

    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path=settings.COOKIE_PATH,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE
    )
    response.delete_cookie(
        key=settings.CSRF_COOKIE_NAME,
        path=settings.COOKIE_PATH,
        httponly=False,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE
    )

    return {"success": True, "message": "Logged out successfully."}


@router.get(
    "/me",
    response_model=SafeUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current Authenticated Profile",
    description="Returns the profile of the authenticated user identified strictly by the server-side session."
)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    """Returns safe user identity without sensitive hashes."""
    return SafeUserResponse.model_validate(current_user)


@router.patch(
    "/me",
    response_model=SafeUserResponse,
    status_code=status.HTTP_200_OK,
    summary="Update User Profile",
    description="Updates permitted profile fields (e.g., full name, facility, registration number)."
)
async def update_me(
    payload: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf)
):
    """Updates permitted profile fields for the authenticated user."""
    updated = await AuthService.update_profile(
        db=db,
        user=current_user,
        full_name=payload.full_name,
        facility_name=payload.facility_name,
        registration_number=payload.registration_number
    )
    return SafeUserResponse.model_validate(updated)
