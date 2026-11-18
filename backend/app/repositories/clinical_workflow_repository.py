import json
from typing import List, Optional, Dict, Any
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.screening_ai import (
    ScreeningAiRun,
    ScreeningAiEyeResult,
    ScreeningAiExplanation,
)
from app.models.clinical_review import ClinicalReview
from app.models.referral import Referral
from app.models.audit_log import ClinicalAuditLog


class ClinicalWorkflowRepository:
    """Data-access layer strictly scoped to owner_user_id for AI runs, reviews, referrals, and audit events."""

    @staticmethod
    async def list_ai_runs_for_screening(
        db: AsyncSession,
        screening_id: str,
        owner_user_id: str,
    ) -> List[ScreeningAiRun]:
        stmt = (
            select(ScreeningAiRun)
            .options(selectinload(ScreeningAiRun.eye_results))
            .where(
                ScreeningAiRun.screening_id == screening_id,
                ScreeningAiRun.owner_user_id == owner_user_id,
            )
            .order_by(desc(ScreeningAiRun.inference_timestamp))
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_latest_ai_run_for_screening(
        db: AsyncSession,
        screening_id: str,
        owner_user_id: str,
    ) -> Optional[ScreeningAiRun]:
        stmt = (
            select(ScreeningAiRun)
            .options(selectinload(ScreeningAiRun.eye_results))
            .where(
                ScreeningAiRun.screening_id == screening_id,
                ScreeningAiRun.owner_user_id == owner_user_id,
            )
            .order_by(desc(ScreeningAiRun.inference_timestamp))
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_ai_run(
        db: AsyncSession,
        run: ScreeningAiRun,
        eye_results: List[ScreeningAiEyeResult],
    ) -> ScreeningAiRun:
        db.add(run)
        await db.flush()
        for eye_res in eye_results:
            eye_res.ai_run_id = run.id
            db.add(eye_res)
        await db.flush()
        await db.refresh(run)
        return run

    @staticmethod
    async def get_clinical_review_for_screening(
        db: AsyncSession,
        screening_id: str,
        owner_user_id: str,
    ) -> Optional[ClinicalReview]:
        stmt = select(ClinicalReview).where(
            ClinicalReview.screening_id == screening_id,
            ClinicalReview.owner_user_id == owner_user_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_clinical_review(
        db: AsyncSession,
        review: ClinicalReview,
    ) -> ClinicalReview:
        db.add(review)
        await db.flush()
        await db.refresh(review)
        return review

    @staticmethod
    async def list_referrals_for_owner(
        db: AsyncSession,
        owner_user_id: str,
        screening_id: Optional[str] = None,
    ) -> List[Referral]:
        stmt = (
            select(Referral)
            .options(selectinload(Referral.patient))
            .where(Referral.owner_user_id == owner_user_id)
            .order_by(desc(Referral.dispatched_at))
        )
        if screening_id:
            stmt = stmt.where(Referral.screening_id == screening_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_referral_by_id(
        db: AsyncSession,
        referral_id: str,
        owner_user_id: str,
    ) -> Optional[Referral]:
        stmt = (
            select(Referral)
            .options(selectinload(Referral.patient))
            .where(
                Referral.id == referral_id,
                Referral.owner_user_id == owner_user_id,
            )
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def create_referral(db: AsyncSession, referral: Referral) -> Referral:
        db.add(referral)
        await db.flush()
        await db.refresh(referral)
        return referral

    @staticmethod
    async def append_audit_log(
        db: AsyncSession,
        *,
        owner_user_id: str,
        actor_user_id: str,
        event_type: str,
        summary: str,
        screening_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ClinicalAuditLog:
        entry = ClinicalAuditLog(
            owner_user_id=owner_user_id,
            actor_user_id=actor_user_id,
            screening_id=screening_id,
            patient_id=patient_id,
            event_type=event_type,
            summary=summary,
            metadata_json=json.dumps(metadata or {}, sort_keys=True),
        )
        db.add(entry)
        await db.flush()
        return entry

    @staticmethod
    async def list_audit_logs_for_screening(
        db: AsyncSession,
        screening_id: str,
        owner_user_id: str,
    ) -> List[ClinicalAuditLog]:
        stmt = (
            select(ClinicalAuditLog)
            .where(
                ClinicalAuditLog.screening_id == screening_id,
                ClinicalAuditLog.owner_user_id == owner_user_id,
            )
            .order_by(ClinicalAuditLog.created_at.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_cached_explanation(
        db: AsyncSession,
        screening_image_id: str,
        checkpoint_sha256: str,
        target_class: int,
    ) -> Optional[ScreeningAiExplanation]:
        stmt = select(ScreeningAiExplanation).where(
            ScreeningAiExplanation.screening_image_id == screening_image_id,
            ScreeningAiExplanation.checkpoint_sha256 == checkpoint_sha256,
            ScreeningAiExplanation.target_class == target_class,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_explanation_by_eye(
        db: AsyncSession,
        screening_id: str,
        owner_user_id: str,
        eye: str,
        target_class: Optional[int] = None,
    ) -> Optional[ScreeningAiExplanation]:
        stmt = select(ScreeningAiExplanation).where(
            ScreeningAiExplanation.screening_id == screening_id,
            ScreeningAiExplanation.owner_user_id == owner_user_id,
            ScreeningAiExplanation.eye == eye,
        )
        if target_class is not None:
            stmt = stmt.where(ScreeningAiExplanation.target_class == target_class)
        else:
            stmt = stmt.where(ScreeningAiExplanation.is_default_target.is_(True))
        stmt = stmt.order_by(desc(ScreeningAiExplanation.created_at)).limit(1)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def list_explanations_for_screening(
        db: AsyncSession,
        screening_id: str,
        owner_user_id: str,
    ) -> List[ScreeningAiExplanation]:
        stmt = (
            select(ScreeningAiExplanation)
            .where(
                ScreeningAiExplanation.screening_id == screening_id,
                ScreeningAiExplanation.owner_user_id == owner_user_id,
            )
            .order_by(ScreeningAiExplanation.eye.asc(), ScreeningAiExplanation.target_class.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def save_explanation(
        db: AsyncSession,
        explanation: ScreeningAiExplanation,
    ) -> ScreeningAiExplanation:
        db.add(explanation)
        await db.flush()
        await db.refresh(explanation)
        return explanation
