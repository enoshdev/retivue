import math
from typing import Optional, List, Dict, Any, Tuple
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.patient import Patient
from app.models.consent import Consent
from app.repositories.patient_repository import PatientRepository
from app.repositories.consent_repository import ConsentRepository
from app.schemas.patient import (
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    PatientListResponse
)
from app.schemas.consent import (
    ConsentCreate,
    ConsentResponse,
    ConsentRevoke
)


class PatientService:
    """Business logic and ownership enforcement for patient operations."""

    @staticmethod
    def _to_patient_response(
        patient: Patient,
        explicit_consent: Optional[Consent] = None,
        screening_count: int = 0
    ) -> PatientResponse:
        """Converts SQLAlchemy model to PatientResponse including active consent."""
        active_consent = None
        if explicit_consent is not None:
            active_consent = ConsentResponse.model_validate(explicit_consent)
        elif "consents" in patient.__dict__ and patient.consents:
            active_consent = ConsentResponse.model_validate(patient.consents[0])

        return PatientResponse(
            id=patient.id,
            owner_user_id=patient.owner_user_id,
            patient_code=patient.patient_code,
            full_name=patient.full_name,
            date_of_birth=patient.date_of_birth,
            sex=patient.sex,
            contact_number=patient.contact_number,
            diabetes_type=patient.diabetes_type,
            diabetes_duration_years=patient.diabetes_duration_years,
            recent_hba1c=patient.recent_hba1c,
            notes=patient.notes,
            is_archived=patient.is_archived,
            created_at=patient.created_at,
            updated_at=patient.updated_at,
            screening_count=screening_count,
            active_consent=active_consent
        )

    @classmethod
    async def create_patient(
        cls,
        db: AsyncSession,
        owner_user_id: str,
        payload: PatientCreate
    ) -> PatientResponse:
        # Create core patient record
        patient = await PatientRepository.create(
            db=db,
            owner_user_id=owner_user_id,
            full_name=payload.full_name,
            patient_code=payload.patient_code,
            date_of_birth=payload.date_of_birth,
            sex=payload.sex,
            contact_number=payload.contact_number,
            diabetes_type=payload.diabetes_type,
            diabetes_duration_years=payload.diabetes_duration_years,
            recent_hba1c=payload.recent_hba1c,
            notes=payload.notes
        )

        # Record initial consent if provided
        initial_consent = None
        if payload.initial_consent:
            initial_consent = await ConsentRepository.create(
                db=db,
                patient_id=patient.id,
                recorded_by_user_id=owner_user_id,
                consent_type=payload.initial_consent.consent_type,
                consent_status=payload.initial_consent.consent_status,
                capture_method=payload.initial_consent.capture_method,
                notes=payload.initial_consent.notes
            )

        return cls._to_patient_response(patient, explicit_consent=initial_consent)

    @classmethod
    async def get_patient(
        cls,
        db: AsyncSession,
        patient_id: str,
        owner_user_id: str
    ) -> PatientResponse:
        patient = await PatientRepository.get_by_id_and_owner(
            db=db,
            patient_id=patient_id,
            owner_user_id=owner_user_id
        )
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient record not found."
            )
        counts = await PatientRepository.get_screening_counts_for_patients(
            db=db,
            owner_user_id=owner_user_id,
            patient_ids=[patient.id]
        )
        return cls._to_patient_response(patient, screening_count=counts.get(patient.id, 0))

    @classmethod
    async def list_patients(
        cls,
        db: AsyncSession,
        owner_user_id: str,
        page: int = 1,
        page_size: int = 20,
        search_query: Optional[str] = None,
        include_archived: bool = False,
        sort_by: str = "created_at",
        sort_order: str = "desc"
    ) -> PatientListResponse:
        items, total = await PatientRepository.list_by_owner(
            db=db,
            owner_user_id=owner_user_id,
            page=page,
            page_size=page_size,
            search_query=search_query,
            include_archived=include_archived,
            sort_by=sort_by,
            sort_order=sort_order
        )

        counts = await PatientRepository.get_screening_counts_for_patients(
            db=db,
            owner_user_id=owner_user_id,
            patient_ids=[p.id for p in items]
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        response_items = [
            cls._to_patient_response(p, screening_count=counts.get(p.id, 0))
            for p in items
        ]

        return PatientListResponse(
            items=response_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages
        )

    @classmethod
    async def update_patient(
        cls,
        db: AsyncSession,
        patient_id: str,
        owner_user_id: str,
        payload: PatientUpdate
    ) -> PatientResponse:
        patient = await PatientRepository.get_by_id_and_owner(
            db=db,
            patient_id=patient_id,
            owner_user_id=owner_user_id
        )
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient record not found."
            )

        updates = payload.model_dump(exclude_unset=True)
        updated = await PatientRepository.update(db, patient, updates)
        return cls._to_patient_response(updated)

    @classmethod
    async def archive_patient(
        cls,
        db: AsyncSession,
        patient_id: str,
        owner_user_id: str
    ) -> PatientResponse:
        patient = await PatientRepository.get_by_id_and_owner(
            db=db,
            patient_id=patient_id,
            owner_user_id=owner_user_id
        )
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient record not found."
            )

        archived = await PatientRepository.archive(db, patient)
        return cls._to_patient_response(archived)

    @classmethod
    async def unarchive_patient(
        cls,
        db: AsyncSession,
        patient_id: str,
        owner_user_id: str
    ) -> PatientResponse:
        patient = await PatientRepository.get_by_id_and_owner(
            db=db,
            patient_id=patient_id,
            owner_user_id=owner_user_id
        )
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient record not found."
            )

        restored = await PatientRepository.unarchive(db, patient)
        return cls._to_patient_response(restored)

    @classmethod
    async def record_consent(
        cls,
        db: AsyncSession,
        patient_id: str,
        owner_user_id: str,
        payload: ConsentCreate
    ) -> ConsentResponse:
        # Verify patient ownership first
        patient = await PatientRepository.get_by_id_and_owner(
            db=db,
            patient_id=patient_id,
            owner_user_id=owner_user_id
        )
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient record not found."
            )

        consent = await ConsentRepository.create(
            db=db,
            patient_id=patient.id,
            recorded_by_user_id=owner_user_id,
            consent_type=payload.consent_type,
            consent_status=payload.consent_status,
            capture_method=payload.capture_method,
            notes=payload.notes
        )
        return ConsentResponse.model_validate(consent)

    @classmethod
    async def revoke_consent(
        cls,
        db: AsyncSession,
        patient_id: str,
        owner_user_id: str,
        payload: ConsentRevoke
    ) -> ConsentResponse:
        # Verify patient ownership first
        patient = await PatientRepository.get_by_id_and_owner(
            db=db,
            patient_id=patient_id,
            owner_user_id=owner_user_id
        )
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient record not found."
            )

        consent = await ConsentRepository.revoke(
            db=db,
            patient_id=patient.id,
            recorded_by_user_id=owner_user_id,
            notes=payload.notes
        )
        return ConsentResponse.model_validate(consent)

    @classmethod
    async def get_consent_history(
        cls,
        db: AsyncSession,
        patient_id: str,
        owner_user_id: str
    ) -> List[ConsentResponse]:
        # Verify patient ownership first
        patient = await PatientRepository.get_by_id_and_owner(
            db=db,
            patient_id=patient_id,
            owner_user_id=owner_user_id
        )
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient record not found."
            )

        consents = await ConsentRepository.list_by_patient(db, patient.id)
        return [ConsentResponse.model_validate(c) for c in consents]
