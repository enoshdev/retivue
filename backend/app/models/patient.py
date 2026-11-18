import uuid
from datetime import datetime, date, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, DateTime, Date, Integer, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.consent import Consent
    from app.models.screening import Screening


class Patient(Base):
    """
    Patient beneficiary record.
    Strictly isolated by owner_user_id (the authenticated clinician or healthcare facility operator).
    """
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    owner_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    patient_code: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        doc="Optional local clinic identifier or Medical Record Number (MRN)"
    )
    full_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    date_of_birth: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True
    )
    sex: Mapped[Optional[str]] = mapped_column(
        String(32),
        nullable=True,
        doc="male, female, other, unknown, undisclosed"
    )
    contact_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    diabetes_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        doc="Type 1, Type 2, Gestational, Other, Unknown"
    )
    diabetes_duration_years: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True
    )
    recent_hba1c: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    owner: Mapped["User"] = relationship(
        "User",
        back_populates="patients"
    )
    consents: Mapped[List["Consent"]] = relationship(
        "Consent",
        back_populates="patient",
        cascade="all, delete-orphan",
        order_by="Consent.captured_at.desc(), Consent.created_at.desc()",
        lazy="selectin"
    )
    screenings: Mapped[List["Screening"]] = relationship(
        "Screening",
        back_populates="patient",
        cascade="all, delete-orphan",
        order_by="Screening.created_at.desc()",
    )

    __table_args__ = (
        Index("ix_patients_owner_archived", "owner_user_id", "is_archived"),
        Index("ix_patients_owner_code", "owner_user_id", "patient_code"),
        Index("ix_patients_owner_created", "owner_user_id", "created_at"),
    )
