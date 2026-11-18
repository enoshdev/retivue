from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User


class UserRepository:
    @staticmethod
    async def get_by_id(db: AsyncSession, user_id: str) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_by_normalized_email(db: AsyncSession, normalized_email: str) -> Optional[User]:
        stmt = select(User).where(User.normalized_email == normalized_email)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create(
        db: AsyncSession,
        full_name: str,
        email: str,
        normalized_email: str,
        password_hash: str,
        facility_name: Optional[str] = None,
        registration_number: Optional[str] = None
    ) -> User:
        user = User(
            full_name=full_name,
            email=email,
            normalized_email=normalized_email,
            password_hash=password_hash,
            facility_name=facility_name,
            registration_number=registration_number,
            is_active=True,
            email_verified=False,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    @staticmethod
    async def update_last_login(db: AsyncSession, user: User) -> None:
        user.last_login_at = datetime.now(timezone.utc)
        user.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)

    @staticmethod
    async def update_profile(
        db: AsyncSession,
        user: User,
        full_name: Optional[str] = None,
        facility_name: Optional[str] = None,
        registration_number: Optional[str] = None
    ) -> User:
        if full_name is not None:
            user.full_name = full_name
        if facility_name is not None:
            user.facility_name = facility_name
        if registration_number is not None:
            user.registration_number = registration_number

        user.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(user)
        return user

