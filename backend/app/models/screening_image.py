import uuid
from datetime import datetime, timezone
from typing import Optional, TYPE_CHECKING
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    Integer,
    BigInteger,
    ForeignKey,
    Index,
    CheckConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.screening import Screening
    from app.models.user import User


class ScreeningImage(Base):
    """
    Auditable bilateral retinal fundus image metadata record (OD or OS).
    Raw original image bytes reside exclusively in private storage referenced by storage_key.
    """
    __tablename__ = "screening_images"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    screening_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("screenings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    eye: Mapped[str] = mapped_column(
        String(2),
        nullable=False,
    )  # Strictly 'OD' or 'OS'
    storage_key: Mapped[str] = mapped_column(
        String(512),
        unique=True,
        nullable=False,
    )
    storage_provider: Mapped[str] = mapped_column(
        String(32),
        default="local",
        nullable=False,
    )
    original_filename: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
    )
    detected_media_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )
    file_extension: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
    )
    file_size_bytes: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )
    image_width: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    image_height: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    sha256_checksum: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )
    has_exif_metadata: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    upload_status: Mapped[str] = mapped_column(
        String(32),
        default="stored",
        nullable=False,
    )  # 'stored', 'replaced', 'deleted'
    is_current: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )
    replaced_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    replaced_by_image_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        nullable=True,
    )

    # Relationships
    screening: Mapped["Screening"] = relationship(
        "Screening",
        back_populates="images",
    )
    owner: Mapped["User"] = relationship(
        "User",
    )

    __table_args__ = (
        CheckConstraint("eye IN ('OD', 'OS')", name="ck_screening_images_eye"),
        CheckConstraint("file_size_bytes > 0", name="ck_screening_images_positive_size"),
        CheckConstraint("image_width > 0 AND image_height > 0", name="ck_screening_images_positive_dims"),
        CheckConstraint("upload_status IN ('stored', 'replaced', 'deleted')", name="ck_screening_images_status"),
        # Enforce at PostgreSQL level: at most ONE current image per (screening_id, eye)
        Index(
            "uq_screening_images_current_eye",
            "screening_id",
            "eye",
            unique=True,
            postgresql_where=text("is_current IS TRUE"),
        ),
        Index("ix_screening_images_owner_screening", "owner_user_id", "screening_id"),
        Index("ix_screening_images_screening_eye_uploaded", "screening_id", "eye", "uploaded_at"),
    )

