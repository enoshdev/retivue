import math
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from fastapi import HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.models.patient import Patient
from app.models.screening import Screening
from app.models.screening_image import ScreeningImage
from app.repositories.consent_repository import ConsentRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.screening_repository import ScreeningRepository
from app.schemas.screening import (
    PatientSummaryResponse,
    ScreeningCreate,
    ScreeningImageResponse,
    ScreeningListResponse,
    ScreeningResponse,
    ScreeningUpdate,
)
from app.services.image_validation import (
    read_upload_with_size_limit,
    validate_and_inspect_image_bytes,
)
from app.storage import ImageStorageBackend, StorageError, generate_storage_key


VALID_EYES = ("OD", "OS")


class ScreeningService:
    """Business logic, strict tenant isolation, consent gate, and storage coordination for screenings."""

    @staticmethod
    def validate_eye_param(eye: str) -> str:
        if eye not in VALID_EYES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Eye parameter must be strictly 'OD' (Right Eye) or 'OS' (Left Eye).",
            )
        return eye

    @staticmethod
    def _to_image_response(img: ScreeningImage) -> ScreeningImageResponse:
        return ScreeningImageResponse.model_validate(img)

    @staticmethod
    def _to_patient_summary(patient: Optional[Patient]) -> Optional[PatientSummaryResponse]:
        if not patient:
            return None
        consent_status = None
        if "consents" in patient.__dict__ and patient.consents:
            consent_status = patient.consents[0].consent_status

        return PatientSummaryResponse(
            id=patient.id,
            patient_code=patient.patient_code,
            full_name=patient.full_name,
            date_of_birth=patient.date_of_birth,
            sex=patient.sex,
            diabetes_type=patient.diabetes_type,
            recent_hba1c=patient.recent_hba1c,
            consent_status=consent_status,
        )

    @classmethod
    def _to_screening_response(cls, screening: Screening) -> ScreeningResponse:
        od_img: Optional[ScreeningImage] = None
        os_img: Optional[ScreeningImage] = None

        if "images" in screening.__dict__ and screening.images:
            for img in screening.images:
                if img.is_current and img.eye == "OD" and od_img is None:
                    od_img = img
                elif img.is_current and img.eye == "OS" and os_img is None:
                    os_img = img

        patient_obj = screening.patient if "patient" in screening.__dict__ else None

        return ScreeningResponse(
            id=screening.id,
            owner_user_id=screening.owner_user_id,
            patient_id=screening.patient_id,
            screening_reference=screening.screening_reference,
            camera_model=screening.camera_model,
            clinical_notes=screening.clinical_notes,
            status=screening.status,
            has_od_image=od_img is not None,
            has_os_image=os_img is not None,
            is_bilateral_complete=(od_img is not None and os_img is not None),
            od_image=cls._to_image_response(od_img) if od_img else None,
            os_image=cls._to_image_response(os_img) if os_img else None,
            patient=cls._to_patient_summary(patient_obj),
            created_at=screening.created_at,
            updated_at=screening.updated_at,
            submitted_at=screening.submitted_at,
            archived_at=screening.archived_at,
        )

    @classmethod
    async def create_screening(
        cls,
        db: AsyncSession,
        owner_user_id: str,
        payload: ScreeningCreate,
    ) -> ScreeningResponse:
        # Strict ownership verification: reject non-existent or another user's patient with 404
        patient = await PatientRepository.get_by_id_and_owner(
            db=db,
            patient_id=payload.patient_id,
            owner_user_id=owner_user_id,
        )
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient record not found.",
            )

        if patient.is_archived:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot initiate screening for an archived patient record.",
            )

        initial_status = "draft" if payload.as_draft else "awaiting_images"
        screening = await ScreeningRepository.create(
            db=db,
            owner_user_id=owner_user_id,
            patient_id=patient.id,
            camera_model=payload.camera_model,
            clinical_notes=payload.clinical_notes,
            initial_status=initial_status,
        )
        return cls._to_screening_response(screening)

    @classmethod
    async def list_screenings(
        cls,
        db: AsyncSession,
        owner_user_id: str,
        page: int = 1,
        page_size: int = 20,
        patient_id: Optional[str] = None,
        status_filter: Optional[str] = None,
        include_archived: bool = False,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> ScreeningListResponse:
        # If patient_id filter provided, ensure caller owns that patient or return empty cleanly
        if patient_id:
            owned_patient = await PatientRepository.get_by_id_and_owner(
                db=db,
                patient_id=patient_id,
                owner_user_id=owner_user_id,
            )
            if not owned_patient:
                return ScreeningListResponse(
                    items=[],
                    total=0,
                    page=page,
                    page_size=page_size,
                    total_pages=0,
                )

        items, total = await ScreeningRepository.list_by_owner(
            db=db,
            owner_user_id=owner_user_id,
            page=page,
            page_size=page_size,
            patient_id=patient_id,
            status_filter=status_filter,
            include_archived=include_archived,
            sort_by=sort_by,
            sort_order=sort_order,
        )
        total_pages = math.ceil(total / page_size) if total > 0 else 0
        return ScreeningListResponse(
            items=[cls._to_screening_response(s) for s in items],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    @classmethod
    async def get_screening(
        cls,
        db: AsyncSession,
        screening_id: str,
        owner_user_id: str,
    ) -> ScreeningResponse:
        screening = await ScreeningRepository.get_by_id_and_owner(
            db=db,
            screening_id=screening_id,
            owner_user_id=owner_user_id,
        )
        if not screening:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Screening record not found.",
            )
        return cls._to_screening_response(screening)

    @classmethod
    async def update_screening(
        cls,
        db: AsyncSession,
        screening_id: str,
        owner_user_id: str,
        payload: ScreeningUpdate,
    ) -> ScreeningResponse:
        screening = await ScreeningRepository.get_by_id_and_owner(
            db=db,
            screening_id=screening_id,
            owner_user_id=owner_user_id,
        )
        if not screening:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Screening record not found.",
            )
        if screening.status in ("cancelled", "archived"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot modify a screening with status '{screening.status}'.",
            )

        updates = payload.model_dump(exclude_unset=True)
        if "camera_model" in updates:
            screening.camera_model = updates["camera_model"].strip() if updates["camera_model"] else None
        if "clinical_notes" in updates:
            screening.clinical_notes = updates["clinical_notes"].strip() if updates["clinical_notes"] else None
        screening.updated_at = datetime.now(timezone.utc)
        await db.commit()
        reloaded = await ScreeningRepository.get_by_id_and_owner(db, screening.id, owner_user_id)
        return cls._to_screening_response(reloaded or screening)

    @classmethod
    async def upload_or_replace_eye_image(
        cls,
        db: AsyncSession,
        storage: ImageStorageBackend,
        screening_id: str,
        owner_user_id: str,
        eye: str,
        file: UploadFile,
        allow_replace: bool = False,
    ) -> Tuple[ScreeningImageResponse, ScreeningResponse]:
        validated_eye = cls.validate_eye_param(eye)

        # 1. Verify screening ownership
        screening = await ScreeningRepository.get_by_id_and_owner(
            db=db,
            screening_id=screening_id,
            owner_user_id=owner_user_id,
        )
        if not screening:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Screening record not found.",
            )

        if screening.status in ("cancelled", "archived"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot upload images to a screening in '{screening.status}' state.",
            )

        # 2. Verify patient still belongs to owner and is valid
        patient = await PatientRepository.get_by_id_and_owner(
            db=db,
            patient_id=screening.patient_id,
            owner_user_id=owner_user_id,
        )
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient record not found.",
            )

        # 3. Check whether a current image already exists for this eye
        existing_current = await ScreeningRepository.get_current_image(
            db=db,
            screening_id=screening.id,
            owner_user_id=owner_user_id,
            eye=validated_eye,
        )
        if existing_current is not None and not allow_replace:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"An image for {validated_eye} is already stored for this screening. "
                    "Use the controlled image replacement endpoint to replace it."
                ),
            )

        # 4. Read and validate actual image content (magic bytes, Pillow decode, dimensions, bomb check)
        raw_bytes = await read_upload_with_size_limit(file, settings.MAX_UPLOAD_SIZE_BYTES)
        validated = validate_and_inspect_image_bytes(
            raw_bytes=raw_bytes,
            claimed_filename=file.filename,
            claimed_content_type=file.content_type,
        )

        # 5. Persist unmodified original bytes to private storage using random key
        storage_key = generate_storage_key(
            screening_id=screening.id,
            eye=validated_eye,
            file_extension=validated.canonical_extension,
        )

        try:
            await storage.save_bytes(
                storage_key=storage_key,
                data=validated.raw_bytes,
                content_type=validated.detected_media_type,
            )
        except StorageError as exc:
            logger.error(f"Storage write failed for screening {screening.id} eye {validated_eye}: {exc.__class__.__name__}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to persist retinal image to private storage.",
            ) from exc

        # 6. Persist metadata record in PostgreSQL transactionally; compensate storage on DB failure
        sid_for_log = screening.id
        try:
            image_record, updated_screening = await ScreeningRepository.save_image_record(
                db=db,
                screening=screening,
                eye=validated_eye,
                storage_key=storage_key,
                storage_provider=storage.provider_name,
                original_filename=validated.sanitized_filename,
                detected_media_type=validated.detected_media_type,
                file_extension=validated.canonical_extension,
                file_size_bytes=validated.file_size_bytes,
                image_width=validated.width,
                image_height=validated.height,
                sha256_checksum=validated.sha256_checksum,
                has_exif_metadata=validated.has_exif_metadata,
                existing_current=existing_current if allow_replace else None,
            )
        except Exception as exc:
            await db.rollback()
            # Compensating delete of the newly created file; previous original (if any) stays untouched
            await storage.delete(storage_key)
            logger.error(
                f"Database write failed for screening {sid_for_log} eye {validated_eye}; "
                f"cleaned up newly written object: {exc.__class__.__name__}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save retinal image metadata cleanly. No partial upload was kept.",
            ) from exc

        return cls._to_image_response(image_record), cls._to_screening_response(updated_screening)

    @classmethod
    async def get_current_eye_image_record(
        cls,
        db: AsyncSession,
        storage: ImageStorageBackend,
        screening_id: str,
        owner_user_id: str,
        eye: str,
    ) -> ScreeningImage:
        validated_eye = cls.validate_eye_param(eye)

        screening = await ScreeningRepository.get_by_id_and_owner(
            db=db,
            screening_id=screening_id,
            owner_user_id=owner_user_id,
        )
        if not screening:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Screening record not found.",
            )

        image = await ScreeningRepository.get_current_image(
            db=db,
            screening_id=screening.id,
            owner_user_id=owner_user_id,
            eye=validated_eye,
        )
        if not image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No {validated_eye} retinal image is currently uploaded for this screening.",
            )

        if not await storage.exists(image.storage_key):
            logger.error(f"Stored retinal image file missing for image ID {image.id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Retinal image object could not be located in private storage.",
            )

        return image

    @classmethod
    async def get_eye_image_history(
        cls,
        db: AsyncSession,
        screening_id: str,
        owner_user_id: str,
        eye: str,
    ) -> List[ScreeningImageResponse]:
        validated_eye = cls.validate_eye_param(eye)
        screening = await ScreeningRepository.get_by_id_and_owner(
            db=db,
            screening_id=screening_id,
            owner_user_id=owner_user_id,
        )
        if not screening:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Screening record not found.",
            )
        history = await ScreeningRepository.list_image_history(
            db=db,
            screening_id=screening.id,
            owner_user_id=owner_user_id,
            eye=validated_eye,
        )
        return [cls._to_image_response(img) for img in history]

    @classmethod
    async def submit_for_quality_assessment(
        cls,
        db: AsyncSession,
        storage: ImageStorageBackend,
        screening_id: str,
        owner_user_id: str,
    ) -> ScreeningResponse:
        # 1. Verify ownership
        screening = await ScreeningRepository.get_by_id_and_owner(
            db=db,
            screening_id=screening_id,
            owner_user_id=owner_user_id,
        )
        if not screening:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Screening record not found.",
            )

        if screening.status in ("cancelled", "archived"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot submit screening in '{screening.status}' state.",
            )

        # 2. Verify patient ownership & active status
        patient = await PatientRepository.get_by_id_and_owner(
            db=db,
            patient_id=screening.patient_id,
            owner_user_id=owner_user_id,
        )
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Patient record not found.",
            )

        # 3. Verify bilateral images exist in DB
        od_img = await ScreeningRepository.get_current_image(db, screening.id, owner_user_id, "OD")
        os_img = await ScreeningRepository.get_current_image(db, screening.id, owner_user_id, "OS")
        if not od_img or not os_img:
            missing = []
            if not od_img:
                missing.append("OD (Right Eye)")
            if not os_img:
                missing.append("OS (Left Eye)")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Bilateral imaging incomplete. Missing required image(s): {', '.join(missing)}.",
            )

        # 4. Verify both original files remain accessible in private storage
        od_exists = await storage.exists(od_img.storage_key)
        os_exists = await storage.exists(os_img.storage_key)
        if not od_exists or not os_exists:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="One or more stored retinal image files could not be verified in private storage.",
            )

        # 5. Strictly verify informed consent is currently granted (reject missing, pending, declined, revoked)
        latest_consent = await ConsentRepository.get_latest_by_patient(
            db=db,
            patient_id=patient.id,
            consent_type="retinal_screening",
        )
        if not latest_consent or latest_consent.consent_status != "granted":
            status_label = latest_consent.consent_status if latest_consent else "missing"
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Cannot submit screening for quality assessment: patient retinal screening consent is "
                    f"'{status_label}'. Valid granted consent is required before processing."
                ),
            )

        # 6. Transition state cleanly (NO ML quality score or AI diagnosis generated here)
        updated = await ScreeningRepository.mark_ready_for_quality_assessment(db, screening)
        return cls._to_screening_response(updated)

    @classmethod
    async def cancel_screening(
        cls,
        db: AsyncSession,
        screening_id: str,
        owner_user_id: str,
    ) -> ScreeningResponse:
        screening = await ScreeningRepository.get_by_id_and_owner(db, screening_id, owner_user_id)
        if not screening:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening record not found.")
        if screening.status == "archived":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Archived screening cannot be cancelled.")
        updated = await ScreeningRepository.update_status(db, screening, "cancelled")
        return cls._to_screening_response(updated)

    @classmethod
    async def archive_screening(
        cls,
        db: AsyncSession,
        screening_id: str,
        owner_user_id: str,
    ) -> ScreeningResponse:
        screening = await ScreeningRepository.get_by_id_and_owner(db, screening_id, owner_user_id)
        if not screening:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening record not found.")
        updated = await ScreeningRepository.update_status(
            db, screening, "archived", archived_at=datetime.now(timezone.utc)
        )
        return cls._to_screening_response(updated)
