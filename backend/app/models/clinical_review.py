import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    Integer,
    Text,
    ForeignKey,
    Index,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.screening import Screening
    from app.models.user import User


class ClinicalReview(Base):
    """
    Independent qualified professional clinical assessment and formal sign-off.
    Strict architectural rule: AI services can NEVER create, mutate, or overwrite this table.
    """

    __tablename__ = "clinical_reviews"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    screening_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("screenings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    owner_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reviewer_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    linked_ai_run_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("screening_ai_runs.id", ondelete="SET NULL"),
        nullable=True,
    )

    reviewer_name_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    reviewer_registration_number_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)

    od_confirmed_grade: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    od_confirmed_label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    os_confirmed_grade: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    os_confirmed_label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    worst_eye_confirmed_grade: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    worst_eye_confirmed_label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    ai_agreement_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )  # 'agreed_with_ai', 'overrode_ai', 'independent_no_ai', 'recapture_ordered'
    override_rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clinical_findings: Mapped[str] = mapped_column(Text, nullable=False)
    follow_up_plan: Mapped[str] = mapped_column(String(100), nullable=False)
    recapture_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    is_signed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    signed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
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

    screening: Mapped["Screening"] = relationship("Screening", back_populates="clinical_review")
    reviewer: Mapped["User"] = relationship("User", foreign_keys=[reviewer_user_id])

    __table_args__ = (
        CheckConstraint(
            "ai_agreement_status IN ('agreed_with_ai', 'overrode_ai', 'independent_no_ai', 'recapture_ordered')",
            name="ck_clinical_reviews_agreement",
        ),
        CheckConstraint(
            "od_confirmed_grade IS NULL OR (od_confirmed_grade >= 0 AND od_confirmed_grade <= 4)",
            name="ck_clinical_reviews_od_grade",
        ),
        CheckConstraint(
            "os_confirmed_grade IS NULL OR (os_confirmed_grade >= 0 AND os_confirmed_grade <= 4)",
            name="ck_clinical_reviews_os_grade",
        ),
        Index("ix_clinical_reviews_owner_signed", "owner_user_id", "signed_at"),
    )

