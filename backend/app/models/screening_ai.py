import uuid
from datetime import datetime, timezone
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import (
    String,
    Boolean,
    DateTime,
    Integer,
    Float,
    Text,
    ForeignKey,
    Index,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database.base import Base

if TYPE_CHECKING:
    from app.models.screening import Screening
    from app.models.screening_image import ScreeningImage
    from app.models.user import User


class ScreeningAiRun(Base):
    """
    Immutable execution record of quality-gated research AI screening on a screening encounter.
    Separated strictly from qualified professional clinical assessments (ClinicalReview).
    """

    __tablename__ = "screening_ai_runs"

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
    triggered_by_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    model_key: Mapped[str] = mapped_column(String(100), nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    architecture: Mapped[str] = mapped_column(String(64), nullable=False)
    checkpoint_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    checkpoint_epoch: Mapped[int] = mapped_column(Integer, nullable=False)
    preprocessing_config_json: Mapped[str] = mapped_column(Text, nullable=False)

    overall_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
        index=True,
    )  # 'completed', 'quality_failed', 'failed'
    overall_review_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    overall_escalation_reasons_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    higher_risk_eye: Mapped[Optional[str]] = mapped_column(String(2), nullable=True)
    highest_predicted_grade: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    highest_predicted_label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    research_disclaimer: Mapped[str] = mapped_column(Text, nullable=False)
    calibration_warning: Mapped[str] = mapped_column(Text, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    execution_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    inference_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    screening: Mapped["Screening"] = relationship("Screening", back_populates="ai_runs")
    triggered_by: Mapped["User"] = relationship("User", foreign_keys=[triggered_by_user_id])
    eye_results: Mapped[List["ScreeningAiEyeResult"]] = relationship(
        "ScreeningAiEyeResult",
        back_populates="ai_run",
        cascade="all, delete-orphan",
        order_by="ScreeningAiEyeResult.eye.asc()",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(
            "overall_status IN ('completed', 'quality_failed', 'failed')",
            name="ck_screening_ai_runs_status",
        ),
        CheckConstraint(
            "higher_risk_eye IS NULL OR higher_risk_eye IN ('OD', 'OS')",
            name="ck_screening_ai_runs_eye",
        ),
        Index("ix_ai_runs_screening_ts", "screening_id", "inference_timestamp"),
        Index("ix_ai_runs_owner_ts", "owner_user_id", "inference_timestamp"),
    )


class ScreeningAiEyeResult(Base):
    """
    Per-eye (OD or OS) hardened quality gate diagnostics and research AI probabilities.
    When gradable is False, predicted_grade and predicted_label MUST remain NULL.
    """

    __tablename__ = "screening_ai_eye_results"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    ai_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("screening_ai_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    screening_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("screenings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    screening_image_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("screening_images.id", ondelete="CASCADE"),
        nullable=False,
    )
    eye: Mapped[str] = mapped_column(String(2), nullable=False)

    gradable: Mapped[bool] = mapped_column(Boolean, nullable=False)
    quality_status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )  # 'gradable', 'ungradable_image_quality', 'decode_error'
    quality_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    quality_metrics_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    predicted_grade: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    predicted_label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    probabilities_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    confidence_max_prob: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    top2_margin: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    normalized_entropy: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    vtdr_prob_sum: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    uncertainty_review_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    uncertainty_reasons_json: Mapped[str] = mapped_column(Text, default="[]", nullable=False)
    high_risk_flagged: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    ai_run: Mapped["ScreeningAiRun"] = relationship("ScreeningAiRun", back_populates="eye_results")
    screening_image: Mapped["ScreeningImage"] = relationship("ScreeningImage")

    __table_args__ = (
        CheckConstraint("eye IN ('OD', 'OS')", name="ck_ai_eye_results_eye"),
        CheckConstraint(
            "quality_status IN ('gradable', 'ungradable_image_quality', 'decode_error')",
            name="ck_ai_eye_results_quality_status",
        ),
        CheckConstraint(
            "(gradable IS TRUE) OR (predicted_grade IS NULL AND predicted_label IS NULL)",
            name="ck_ai_eye_results_no_forced_grade",
        ),
        Index("uq_ai_eye_results_run_eye", "ai_run_id", "eye", unique=True),
    )


class ScreeningAiExplanation(Base):
    """
    Genuine Grad-CAM activation explanation artifact record for a retinal fundus image.
    Records model layer, target class, raw scores, explanation text, and storage pointers.
    """

    __tablename__ = "screening_ai_explanations"

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
    screening_image_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("screening_images.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ai_run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("screening_ai_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    eye: Mapped[str] = mapped_column(String(2), nullable=False)  # 'OD' | 'OS'
    target_class: Mapped[int] = mapped_column(Integer, nullable=False)  # 0 to 4
    target_class_label: Mapped[str] = mapped_column(String(64), nullable=False)
    is_default_target: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(
        String(40),
        nullable=False,
    )  # 'completed', 'unavailable_ungradable', 'failed'
    explanation_text: Mapped[str] = mapped_column(Text, nullable=False)
    model_layer: Mapped[str] = mapped_column(String(64), default="features.8", nullable=False)
    image_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    checkpoint_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    heatmap_storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    overlay_storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    screening: Mapped["Screening"] = relationship("Screening")
    screening_image: Mapped["ScreeningImage"] = relationship("ScreeningImage")
    ai_run: Mapped["ScreeningAiRun"] = relationship("ScreeningAiRun")
    owner: Mapped["User"] = relationship("User")

    __table_args__ = (
        CheckConstraint("eye IN ('OD', 'OS')", name="ck_ai_explanations_eye"),
        CheckConstraint("target_class BETWEEN 0 AND 4", name="ck_ai_explanations_target_class"),
        CheckConstraint(
            "status IN ('completed', 'unavailable_ungradable', 'failed')",
            name="ck_ai_explanations_status",
        ),
        Index("ix_ai_explanations_lookup", "screening_id", "eye", "target_class"),
        Index("uq_ai_explanations_cache", "screening_image_id", "checkpoint_sha256", "target_class", unique=True),
    )


