import uuid
import secrets
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from sqlalchemy import select, func, desc, asc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.screening import Screening
from app.models.screening_image import ScreeningImage
from app.models.patient import Patient


def generate_screening_reference() -> str:
    """Generate a unique human-readable clinical screening reference, e.g. SCR-20261110-A1B2C3."""
    date_part = datetime.now(timezone.utc).strftime("%Y%m%d")
    rand_part = secrets.token_hex(3).upper()
    return f"SCR-{date_part}-{rand_part}"


class ScreeningRepository:
    """Handles PostgreSQL persistence and strict owner-isolated queries for screenings and images."""

    @staticmethod
    async def create(
        db: AsyncSession,
        owner_user_id: str,
        patient_id: str,
        camera_model: Optional[str] = None,
        clinical_notes: Optional[str] = None,
        initial_status: str = "awaiting_images",
    ) -> Screening:
        now = datetime.now(timezone.utc)
        screening = Screening(
            id=str(uuid.uuid4()),
            owner_user_id=owner_user_id,
            patient_id=patient_id,
            screening_reference=generate_screening_reference(),
            camera_model=camera_model.strip() if camera_model else None,
            clinical_notes=clinical_notes.strip() if clinical_notes else None,
            status=initial_status,
            created_at=now,
            updated_at=now,
        )
        db.add(screening)
        await db.commit()
        reloaded = await ScreeningRepository.get_by_id_and_owner(db, screening.id, owner_user_id)
        return reloaded or screening

    @staticmethod
    async def get_by_id_and_owner(
        db: AsyncSession,
        screening_id: str,
        owner_user_id: str,
    ) -> Optional[Screening]:
        """
        Retrieve a screening strictly filtered by both screening_id and owner_user_id.
        Eagerly loads patient (+ consents) and screening images.
        """
        stmt = (
            select(Screening)
            .options(
                selectinload(Screening.patient).selectinload(Patient.consents),
                selectinload(Screening.images),
            )
            .where(
                Screening.id == screening_id,
                Screening.owner_user_id == owner_user_id,
            )
            .execution_options(populate_existing=True)
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_by_owner(
        db: AsyncSession,
        owner_user_id: str,
        page: int = 1,
        page_size: int = 20,
        patient_id: Optional[str] = None,
        status_filter: Optional[str] = None,
        include_archived: bool = False,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> Tuple[List[Screening], int]:
        page = max(1, page)
        page_size = min(max(1, page_size), 100)

        filters = [Screening.owner_user_id == owner_user_id]

        if patient_id:
            filters.append(Screening.patient_id == patient_id)

        if status_filter:
            filters.append(Screening.status == status_filter)
        elif not include_archived:
            filters.append(Screening.status != "archived")

        count_stmt = select(func.count()).select_from(Screening).where(*filters)
        total_res = await db.execute(count_stmt)
        total_count = total_res.scalar() or 0

        order_col = Screening.created_at
        if sort_by == "updated_at":
            order_col = Screening.updated_at
        elif sort_by == "submitted_at":
            order_col = Screening.submitted_at

        order_expr = desc(order_col) if sort_order.lower() == "desc" else asc(order_col)

        items_stmt = (
            select(Screening)
            .options(
                selectinload(Screening.patient).selectinload(Patient.consents),
                selectinload(Screening.images),
            )
            .where(*filters)
            .order_by(order_expr)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items_res = await db.execute(items_stmt)
        items = list(items_res.scalars().all())
        return items, total_count

    @staticmethod
    async def get_current_image(
        db: AsyncSession,
        screening_id: str,
        owner_user_id: str,
        eye: str,
    ) -> Optional[ScreeningImage]:
        stmt = (
            select(ScreeningImage)
            .where(
                ScreeningImage.screening_id == screening_id,
                ScreeningImage.owner_user_id == owner_user_id,
                ScreeningImage.eye == eye,
                ScreeningImage.is_current.is_(True),
            )
            .limit(1)
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    @staticmethod
    async def list_image_history(
        db: AsyncSession,
        screening_id: str,
        owner_user_id: str,
        eye: str,
    ) -> List[ScreeningImage]:
        stmt = (
            select(ScreeningImage)
            .where(
                ScreeningImage.screening_id == screening_id,
                ScreeningImage.owner_user_id == owner_user_id,
                ScreeningImage.eye == eye,
            )
            .order_by(desc(ScreeningImage.uploaded_at))
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def save_image_record(
        db: AsyncSession,
        screening: Screening,
        eye: str,
        storage_key: str,
        storage_provider: str,
        original_filename: str,
        detected_media_type: str,
        file_extension: str,
        file_size_bytes: int,
        image_width: int,
        image_height: int,
        sha256_checksum: str,
        has_exif_metadata: bool,
        existing_current: Optional[ScreeningImage] = None,
    ) -> Tuple[ScreeningImage, Screening]:
        """
        Transactionally inserts a new current ScreeningImage record, optionally retiring
        the previous current image for the same eye while keeping its audit row intact.
        Updates screening lifecycle status accurately.
        """
        now = datetime.now(timezone.utc)
        new_image_id = str(uuid.uuid4())

        if existing_current is not None:
            existing_current.is_current = False
            existing_current.upload_status = "replaced"
            existing_current.replaced_at = now
            existing_current.replaced_by_image_id = new_image_id
            # Flush first so partial unique index (screening_id, eye) WHERE is_current IS TRUE allows insert
            await db.flush()

        new_image = ScreeningImage(
            id=new_image_id,
            screening_id=screening.id,
            owner_user_id=screening.owner_user_id,
            eye=eye,
            storage_key=storage_key,
            storage_provider=storage_provider,
            original_filename=original_filename,
            detected_media_type=detected_media_type,
            file_extension=file_extension,
            file_size_bytes=file_size_bytes,
            image_width=image_width,
            image_height=image_height,
            sha256_checksum=sha256_checksum,
            has_exif_metadata=has_exif_metadata,
            uploaded_at=now,
            upload_status="stored",
            is_current=True,
        )
        db.add(new_image)
        await db.flush()

        # Recompute current eyes for lifecycle status
        current_stmt = select(ScreeningImage.eye).where(
            ScreeningImage.screening_id == screening.id,
            ScreeningImage.is_current.is_(True),
        )
        eye_res = await db.execute(current_stmt)
        active_eyes = set(eye_res.scalars().all())

        if "OD" in active_eyes and "OS" in active_eyes:
            screening.status = "draft"
        else:
            screening.status = "images_incomplete"

        # If previously submitted and now updated/replaced, reset submitted_at so explicit re-submission happens
        if screening.submitted_at is not None:
            screening.submitted_at = None

        screening.updated_at = now
        await db.commit()

        reloaded_screening = await ScreeningRepository.get_by_id_and_owner(
            db, screening.id, screening.owner_user_id
        )
        await db.refresh(new_image)
        return new_image, (reloaded_screening or screening)

    @staticmethod
    async def mark_ready_for_quality_assessment(
        db: AsyncSession,
        screening: Screening,
    ) -> Screening:
        now = datetime.now(timezone.utc)
        screening.status = "ready_for_quality_assessment"
        screening.submitted_at = now
        screening.updated_at = now
        await db.commit()
        reloaded = await ScreeningRepository.get_by_id_and_owner(
            db, screening.id, screening.owner_user_id
        )
        return reloaded or screening

    @staticmethod
    async def update_status(
        db: AsyncSession,
        screening: Screening,
        new_status: str,
        archived_at: Optional[datetime] = None,
    ) -> Screening:
        now = datetime.now(timezone.utc)
        screening.status = new_status
        if archived_at is not None:
            screening.archived_at = archived_at
        screening.updated_at = now
        await db.commit()
        reloaded = await ScreeningRepository.get_by_id_and_owner(
            db, screening.id, screening.owner_user_id
        )
        return reloaded or screening
