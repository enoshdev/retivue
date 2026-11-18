from datetime import datetime, timedelta, timezone
from typing import Tuple, Optional
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User
from app.models.session import UserSession
from app.repositories.user_repository import UserRepository
from app.repositories.session_repository import SessionRepository
from app.core.security import (
    normalize_email,
    hash_password,
    verify_password,
    generate_session_token,
    hash_session_token,
)
from app.core.config import settings
from app.core.logging import logger


class AuthService:
    @staticmethod
    async def register_user(
        db: AsyncSession,
        full_name: str,
        email: str,
        password: str,
        facility_name: Optional[str] = None,
        registration_number: Optional[str] = None
    ) -> Tuple[User, str]:
        norm_email = normalize_email(email)

        # Duplicate email check
        existing = await UserRepository.get_by_normalized_email(db, norm_email)
        if existing:
            logger.warning(f"Registration rejected: duplicate normalized email attempt.")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email address already exists."
            )

        # Argon2id password hash
        try:
            pwd_hash = hash_password(password)
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(err)
            )

        user = await UserRepository.create(
            db=db,
            full_name=full_name.strip(),
            email=email.strip(),
            normalized_email=norm_email,
            password_hash=pwd_hash,
            facility_name=facility_name.strip() if facility_name else None,
            registration_number=registration_number.strip() if registration_number else None
        )

        # Create persistent session
        raw_token = generate_session_token()
        token_hash = hash_session_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.SESSION_MAX_AGE_SECONDS)

        await SessionRepository.create(
            db=db,
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at
        )

        logger.info(f"User registration successful: user_id={user.id}")
        return user, raw_token

    @staticmethod
    async def login_user(
        db: AsyncSession,
        email: str,
        password: str
    ) -> Tuple[User, str]:
        norm_email = normalize_email(email)
        user = await UserRepository.get_by_normalized_email(db, norm_email)

        # Generic authentication failure message for both unknown email & wrong password
        if not user or not user.is_active:
            logger.warning("Login failed: invalid email or inactive account.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )

        if not verify_password(password, user.password_hash):
            logger.warning(f"Login failed: invalid password for user_id={user.id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password."
            )

        # Create persistent session
        raw_token = generate_session_token()
        token_hash = hash_session_token(raw_token)
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=settings.SESSION_MAX_AGE_SECONDS)

        await SessionRepository.create(
            db=db,
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at
        )

        await UserRepository.update_last_login(db, user)
        logger.info(f"User login successful: user_id={user.id}")
        return user, raw_token

    @staticmethod
    async def logout_session(
        db: AsyncSession,
        session: UserSession
    ) -> None:
        await SessionRepository.revoke(db, session)
        logger.info(f"Session revoked for user_id={session.user_id}")

    @staticmethod
    async def update_profile(
        db: AsyncSession,
        user: User,
        full_name: Optional[str] = None,
        facility_name: Optional[str] = None,
        registration_number: Optional[str] = None
    ) -> User:
        updated = await UserRepository.update_profile(
            db=db,
            user=user,
            full_name=full_name.strip() if full_name else None,
            facility_name=facility_name.strip() if facility_name else None,
            registration_number=registration_number.strip() if registration_number else None
        )
        logger.info(f"User profile updated: user_id={user.id}")
        return updated

