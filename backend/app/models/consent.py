import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.user import User


class Consent(Base):
    """
    Auditable patient informed consent record for clinical screening operations.
    Maintains historical consent state changes (granted, declined, revoked).
    """
    __tablename__ = "consents"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    patient_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("patients.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    recorded_by_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    consent_type: Mapped[str] = mapped_column(
        String(100),
        default="retinal_screening",
        nullable=False
    )
    consent_status: Mapped[str] = mapped_column(
        String(50),
        default="granted",
        nullable=False
    )  # 'pending', 'granted', 'declined', 'revoked'
    capture_method: Mapped[str] = mapped_column(
        String(100),
        default="digital_acknowledgement",
        nullable=False
    )  # 'written_form', 'verbal_recorded', 'digital_acknowledgement', 'direct_clinical_intake'
    captured_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    patient: Mapped["Patient"] = relationship(
        "Patient",
        back_populates="consents"
    )
    recorded_by: Mapped["User"] = relationship(
        "User"
    )

    __table_args__ = (
        Index("ix_consents_patient_captured", "patient_id", "captured_at"),
    )

