from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.consent import Consent


class ConsentRepository:
    """Handles database persistence for clinical informed consent audit logs."""

    @staticmethod
    async def create(
        db: AsyncSession,
        patient_id: str,
        recorded_by_user_id: str,
        consent_type: str = "retinal_screening",
        consent_status: str = "granted",
        capture_method: str = "digital_acknowledgement",
        notes: Optional[str] = None
    ) -> Consent:
        now = datetime.now(timezone.utc)
        consent = Consent(
            patient_id=patient_id,
            recorded_by_user_id=recorded_by_user_id,
            consent_type=consent_type,
            consent_status=consent_status,
            capture_method=capture_method,
            captured_at=now,
            notes=notes,
            created_at=now
        )
        db.add(consent)
        await db.commit()
        await db.refresh(consent)
        return consent

    @staticmethod
    async def list_by_patient(
        db: AsyncSession,
        patient_id: str
    ) -> List[Consent]:
        stmt = (
            select(Consent)
            .where(Consent.patient_id == patient_id)
            .order_by(desc(Consent.captured_at), desc(Consent.created_at))
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def get_latest_by_patient(
        db: AsyncSession,
        patient_id: str,
        consent_type: str = "retinal_screening"
    ) -> Optional[Consent]:
        stmt = (
            select(Consent)
            .where(
                Consent.patient_id == patient_id,
                Consent.consent_type == consent_type,
            )
            .order_by(desc(Consent.captured_at), desc(Consent.created_at))
            .limit(1)
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def revoke(
        db: AsyncSession,
        patient_id: str,
        recorded_by_user_id: str,
        notes: Optional[str] = None
    ) -> Consent:
        """
        Records an auditable revocation event in the consent history
        without destroying earlier consent records.
        """
        now = datetime.now(timezone.utc)
        revocation_entry = Consent(
            patient_id=patient_id,
            recorded_by_user_id=recorded_by_user_id,
            consent_type="retinal_screening",
            consent_status="revoked",
            capture_method="direct_clinical_intake",
            captured_at=now,
            revoked_at=now,
            notes=notes or "Patient requested informed consent revocation",
            created_at=now
        )
        db.add(revocation_entry)
        await db.commit()
        await db.refresh(revocation_entry)
        return revocation_entry

