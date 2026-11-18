from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.session import UserSession
from app.models.user import User


class SessionRepository:
    @staticmethod
    async def create(
        db: AsyncSession,
        user_id: str,
        token_hash: str,
        expires_at: datetime
    ) -> UserSession:
        now = datetime.now(timezone.utc)
        session = UserSession(
            user_id=user_id,
            token_hash=token_hash,
            created_at=now,
            last_used_at=now,
            expires_at=expires_at,
            revoked_at=None
        )
        db.add(session)
        await db.commit()
        await db.refresh(session)
        return session

    @staticmethod
    async def get_active_session_by_token_hash(
        db: AsyncSession,
        token_hash: str
    ) -> Optional[UserSession]:
        now = datetime.now(timezone.utc)
        stmt = (
            select(UserSession)
            .options(selectinload(UserSession.user))
            .where(
                and_(
                    UserSession.token_hash == token_hash,
                    UserSession.revoked_at.is_(None),
                    UserSession.expires_at > now
                )
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def touch(db: AsyncSession, session: UserSession) -> None:
        session.last_used_at = datetime.now(timezone.utc)
        await db.commit()

    @staticmethod
    async def revoke(db: AsyncSession, session: UserSession) -> None:
        session.revoked_at = datetime.now(timezone.utc)
        await db.commit()

