import math
from datetime import datetime, date, timezone
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, func, or_, desc, asc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.patient import Patient
from app.models.consent import Consent
from app.models.screening import Screening


class PatientRepository:
    """Handles PostgreSQL persistence and strict owner-isolated queries for patients."""

    @staticmethod
    async def create(
        db: AsyncSession,
        owner_user_id: str,
        full_name: str,
        patient_code: Optional[str] = None,
        date_of_birth: Optional[date] = None,
        sex: Optional[str] = None,
        contact_number: Optional[str] = None,
        diabetes_type: Optional[str] = None,
        diabetes_duration_years: Optional[int] = None,
        recent_hba1c: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> Patient:
        now = datetime.now(timezone.utc)
        patient = Patient(
            owner_user_id=owner_user_id,
            full_name=full_name.strip(),
            patient_code=patient_code.strip() if patient_code else None,
            date_of_birth=date_of_birth,
            sex=sex,
            contact_number=contact_number.strip() if contact_number else None,
            diabetes_type=diabetes_type,
            diabetes_duration_years=diabetes_duration_years,
            recent_hba1c=recent_hba1c.strip() if recent_hba1c else None,
            notes=notes,
            is_archived=False,
            created_at=now,
            updated_at=now
        )
        db.add(patient)
        await db.commit()
        await db.refresh(patient, attribute_names=[c.name for c in Patient.__table__.columns])
        return patient

    @staticmethod
    async def get_by_id_and_owner(
        db: AsyncSession,
        patient_id: str,
        owner_user_id: str
    ) -> Optional[Patient]:
        """
        Retrieves a patient strictly filtered by both patient_id and owner_user_id.
        Prevents IDOR and cross-account disclosure.
        """
        stmt = (
            select(Patient)
            .options(selectinload(Patient.consents))
            .where(
                Patient.id == patient_id,
                Patient.owner_user_id == owner_user_id
            )
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_by_owner(
        db: AsyncSession,
        owner_user_id: str,
        page: int = 1,
        page_size: int = 20,
        search_query: Optional[str] = None,
        include_archived: bool = False,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> Tuple[List[Patient], int]:
        """
        Retrieves paginated patient records owned exclusively by owner_user_id.
        """
        page = max(1, page)
        page_size = min(max(1, page_size), 100)

        # Base query filters
        filters = [Patient.owner_user_id == owner_user_id]
        if not include_archived:
            filters.append(Patient.is_archived.is_(False))

        if search_query and search_query.strip():
            q = f"%{search_query.strip()}%"
            filters.append(
                or_(
                    Patient.full_name.ilike(q),
                    Patient.patient_code.ilike(q),
                    Patient.contact_number.ilike(q)
                )
            )

        # Count total matching
        count_stmt = select(func.count()).select_from(Patient).where(*filters)
        total_res = await db.execute(count_stmt)
        total_count = total_res.scalar() or 0

        # Sorting
        order_col = Patient.created_at
        if sort_by == "name":
            order_col = Patient.full_name
        elif sort_by == "updated_at":
            order_col = Patient.updated_at

        order_expr = desc(order_col) if sort_order.lower() == "desc" else asc(order_col)

        # Items query with latest consents eagerly loaded
        items_stmt = (
            select(Patient)
            .options(selectinload(Patient.consents))
            .where(*filters)
            .order_by(order_expr)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items_res = await db.execute(items_stmt)
        items = list(items_res.scalars().all())

        return items, total_count

    @staticmethod
    async def update(
        db: AsyncSession,
        patient: Patient,
        updates: Dict[str, Any]
    ) -> Patient:
        """Applies validated updates and updates updated_at timestamp."""
        for field, value in updates.items():
            if hasattr(patient, field) and field not in ("id", "owner_user_id", "created_at"):
                setattr(patient, field, value)

        patient.updated_at = datetime.now(timezone.utc)
        await db.commit()
        reloaded = await PatientRepository.get_by_id_and_owner(db, patient.id, patient.owner_user_id)
        return reloaded or patient

    @staticmethod
    async def archive(
        db: AsyncSession,
        patient: Patient
    ) -> Patient:
        """Soft-archives patient record."""
        patient.is_archived = True
        patient.updated_at = datetime.now(timezone.utc)
        await db.commit()
        reloaded = await PatientRepository.get_by_id_and_owner(db, patient.id, patient.owner_user_id)
        return reloaded or patient

    @staticmethod
    async def unarchive(
        db: AsyncSession,
        patient: Patient
    ) -> Patient:
        """Restores an archived patient record."""
        patient.is_archived = False
        patient.updated_at = datetime.now(timezone.utc)
        await db.commit()
        reloaded = await PatientRepository.get_by_id_and_owner(db, patient.id, patient.owner_user_id)
        return reloaded or patient

    @staticmethod
    async def get_screening_counts_for_patients(
        db: AsyncSession,
        owner_user_id: str,
        patient_ids: List[str]
    ) -> Dict[str, int]:
        """Return count of non-archived screenings per patient scoped by owner_user_id."""
        if not patient_ids:
            return {}
        stmt = (
            select(Screening.patient_id, func.count(Screening.id))
            .where(
                Screening.owner_user_id == owner_user_id,
                Screening.patient_id.in_(patient_ids),
                Screening.status != "archived",
            )
            .group_by(Screening.patient_id)
        )
        res = await db.execute(stmt)
        return {row[0]: int(row[1]) for row in res.all()}
