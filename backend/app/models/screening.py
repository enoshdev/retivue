import uuid
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, DateTime, Text, ForeignKey, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.patient import Patient
    from app.models.screening_image import ScreeningImage
    from app.models.screening_ai import ScreeningAiRun
    from app.models.clinical_review import ClinicalReview
    from app.models.referral import Referral


SCREENING_VALID_STATUSES = (
    "draft",
    "awaiting_images",
    "images_incomplete",
    "ready_for_quality_assessment",
    "quality_failed_recapture_required",
    "ai_completed_review_required",
    "ai_completed_advisory",
    "ai_failed_review_required",
    "clinically_reviewed_signed",
    "cancelled",
    "archived",
)


class Screening(Base):
    """
    Diabetic retinopathy screening encounter belonging strictly to one owner user
    and one patient beneficiary.
    """
    __tablename__ = "screenings"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    owner_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    screening_reference: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    camera_model: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    clinical_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(50),
        default="awaiting_images",
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    archived_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="screenings",
    )
    patient: Mapped["Patient"] = relationship(
        "Patient",
        back_populates="screenings",
        lazy="selectin",
    )
    images: Mapped[List["ScreeningImage"]] = relationship(
        "ScreeningImage",
        back_populates="screening",
        cascade="all, delete-orphan",
        order_by="ScreeningImage.uploaded_at.desc()",
        lazy="selectin",
    )
    ai_runs: Mapped[List["ScreeningAiRun"]] = relationship(
        "ScreeningAiRun",
        back_populates="screening",
        cascade="all, delete-orphan",
        order_by="ScreeningAiRun.inference_timestamp.desc()",
        lazy="selectin",
    )
    clinical_review: Mapped[Optional["ClinicalReview"]] = relationship(
        "ClinicalReview",
        back_populates="screening",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    referrals: Mapped[List["Referral"]] = relationship(
        "Referral",
        back_populates="screening",
        cascade="all, delete-orphan",
        order_by="Referral.dispatched_at.desc()",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft', 'awaiting_images', 'images_incomplete', "
            "'ready_for_quality_assessment', 'quality_failed_recapture_required', "
            "'ai_completed_review_required', 'ai_completed_advisory', "
            "'ai_failed_review_required', 'clinically_reviewed_signed', "
            "'cancelled', 'archived')",
            name="ck_screenings_status",
        ),
        Index("ix_screenings_owner_status", "owner_user_id", "status"),
        Index("ix_screenings_owner_patient", "owner_user_id", "patient_id"),
        Index("ix_screenings_owner_created", "owner_user_id", "created_at"),
    )

