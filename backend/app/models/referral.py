import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, DateTime, Text, ForeignKey, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.screening import Screening
    from app.models.patient import Patient
    from app.models.clinical_review import ClinicalReview
    from app.models.user import User


class Referral(Base):
    """
    Ophthalmology / tertiary-care specialist referral created strictly after independent clinical sign-off.
    """

    __tablename__ = "referrals"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    referral_reference: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    screening_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("screenings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    clinical_review_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("clinical_reviews.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    patient_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    urgency: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
    )  # 'IMMEDIATE_48H', 'WITHIN_2_WEEKS', 'STANDARD_SURVEILLANCE'
    target_specialty: Mapped[str] = mapped_column(String(120), nullable=False)
    target_facility: Mapped[str] = mapped_column(String(255), nullable=False)
    reason_summary: Mapped[str] = mapped_column(Text, nullable=False)
    clinical_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        String(40),
        default="DISPATCHED",
        nullable=False,
        index=True,
    )  # 'DISPATCHED', 'ACCEPTED', 'APPOINTMENT_SCHEDULED', 'COMPLETED', 'CANCELLED'
    appointment_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dispatched_at: Mapped[datetime] = mapped_column(
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

    screening: Mapped["Screening"] = relationship("Screening", back_populates="referrals")
    patient: Mapped["Patient"] = relationship("Patient")
    clinical_review: Mapped["ClinicalReview"] = relationship("ClinicalReview")
    created_by: Mapped["User"] = relationship("User", foreign_keys=[created_by_user_id])

    __table_args__ = (
        CheckConstraint(
            "urgency IN ('IMMEDIATE_48H', 'WITHIN_2_WEEKS', 'STANDARD_SURVEILLANCE')",
            name="ck_referrals_urgency",
        ),
        CheckConstraint(
            "status IN ('DISPATCHED', 'ACCEPTED', 'APPOINTMENT_SCHEDULED', 'COMPLETED', 'CANCELLED')",
            name="ck_referrals_status",
        ),
        Index("ix_referrals_owner_dispatched", "owner_user_id", "dispatched_at"),
    )

