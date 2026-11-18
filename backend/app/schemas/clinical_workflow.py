from datetime import datetime
from typing import Dict, List, Literal, Optional, Any
from pydantic import BaseModel, Field, field_validator, model_validator


class AiModelRegistryItem(BaseModel):
    model_key: str
    model_version: str
    architecture: str
    training_strategy: str
    checkpoint_sha256: str
    checkpoint_epoch: int
    is_default: bool
    checkpoint_present: bool
    status_note: str


class AiInferenceRequest(BaseModel):
    model_key: Optional[str] = Field(
        default=None,
        description="Preserved research checkpoint key (E0/E1/E2). Defaults to operator-configured E2.",
    )


class AiExplanationResponse(BaseModel):
    id: str
    screening_id: str
    screening_image_id: str
    ai_run_id: str
    eye: str
    target_class: int
    target_class_label: str
    is_default_target: bool
    status: str  # 'completed', 'unavailable_ungradable', 'failed'
    explanation_text: str
    model_layer: str
    image_sha256: str
    checkpoint_sha256: str
    has_heatmap: bool
    has_overlay: bool
    created_at: datetime


class AiExplanationRegenerateRequest(BaseModel):
    target_class: Optional[int] = Field(default=None, ge=0, le=4)


class AiEyeResultResponse(BaseModel):
    id: str
    eye: str
    screening_image_id: str
    gradable: bool
    quality_status: str
    quality_reason: Optional[str] = None
    quality_metrics: Dict[str, Any]
    predicted_grade: Optional[int] = None
    predicted_label: Optional[str] = None
    probabilities: Dict[str, float]
    confidence_max_prob: Optional[float] = None
    top2_margin: Optional[float] = None
    normalized_entropy: Optional[float] = None
    vtdr_prob_sum: Optional[float] = None
    uncertainty_review_required: bool
    uncertainty_reasons: List[str]
    high_risk_flagged: bool
    explanation: Optional[AiExplanationResponse] = None


class AiRunResponse(BaseModel):
    id: str
    screening_id: str
    model_key: str
    model_version: str
    architecture: str
    checkpoint_sha256: str
    checkpoint_epoch: int
    preprocessing_config: Dict[str, Any]
    overall_status: str
    overall_review_required: bool
    overall_escalation_reasons: List[str]
    higher_risk_eye: Optional[str] = None
    highest_predicted_grade: Optional[int] = None
    highest_predicted_label: Optional[str] = None
    research_disclaimer: str
    calibration_warning: str
    error_message: Optional[str] = None
    execution_ms: int
    inference_timestamp: datetime
    eye_results: List[AiEyeResultResponse]


class ClinicalReviewCreate(BaseModel):
    od_confirmed_grade: Optional[int] = Field(default=None, ge=0, le=4)
    os_confirmed_grade: Optional[int] = Field(default=None, ge=0, le=4)
    ai_agreement_status: Literal[
        "agreed_with_ai",
        "overrode_ai",
        "independent_no_ai",
        "recapture_ordered",
    ]
    override_rationale: Optional[str] = Field(default=None, max_length=2000)
    clinical_findings: str = Field(..., min_length=5, max_length=4000)
    follow_up_plan: str = Field(..., min_length=2, max_length=200)
    recapture_required: bool = False
    confirm_independent_review: bool = Field(
        ...,
        description="Practitioner attestation that findings were independently reviewed.",
    )

    @field_validator("confirm_independent_review")
    @classmethod
    def must_confirm_independent_review(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Practitioner must confirm independent clinical review before sign-off.")
        return v

    @model_validator(mode="after")
    def validate_grades_and_rationale(self):
        if self.ai_agreement_status == "overrode_ai":
            if not self.override_rationale or len(self.override_rationale.strip()) < 5:
                raise ValueError("An override rationale (>= 5 characters) is required when overriding AI advisory.")
        if not self.recapture_required and self.ai_agreement_status != "recapture_ordered":
            if self.od_confirmed_grade is None and self.os_confirmed_grade is None:
                raise ValueError("Confirm at least one eye DR grade or mark recapture_required=true.")
        return self


class ClinicalReviewResponse(BaseModel):
    id: str
    screening_id: str
    reviewer_user_id: str
    reviewer_name_snapshot: str
    reviewer_registration_number_snapshot: str
    linked_ai_run_id: Optional[str] = None
    od_confirmed_grade: Optional[int] = None
    od_confirmed_label: Optional[str] = None
    os_confirmed_grade: Optional[int] = None
    os_confirmed_label: Optional[str] = None
    worst_eye_confirmed_grade: Optional[int] = None
    worst_eye_confirmed_label: Optional[str] = None
    ai_agreement_status: str
    override_rationale: Optional[str] = None
    clinical_findings: str
    follow_up_plan: str
    recapture_required: bool
    is_signed: bool
    signed_at: datetime
    created_at: datetime


class ReferralCreate(BaseModel):
    screening_id: str
    urgency: Literal["IMMEDIATE_48H", "WITHIN_2_WEEKS", "STANDARD_SURVEILLANCE"]
    target_specialty: str = Field(..., min_length=3, max_length=120)
    target_facility: str = Field(..., min_length=3, max_length=255)
    reason_summary: str = Field(..., min_length=5, max_length=2000)
    clinical_summary: Optional[str] = Field(default=None, max_length=4000)


class ReferralStatusUpdate(BaseModel):
    status: Literal[
        "DISPATCHED",
        "ACCEPTED",
        "APPOINTMENT_SCHEDULED",
        "COMPLETED",
        "CANCELLED",
    ]
    appointment_notes: Optional[str] = Field(default=None, max_length=2000)


class ReferralResponse(BaseModel):
    id: str
    referral_reference: str
    screening_id: str
    clinical_review_id: str
    patient_id: str
    patient_name: Optional[str] = None
    patient_mrn: Optional[str] = None
    urgency: str
    target_specialty: str
    target_facility: str
    reason_summary: str
    clinical_summary: Optional[str] = None
    status: str
    appointment_notes: Optional[str] = None
    dispatched_at: datetime
    updated_at: datetime


class AuditLogResponse(BaseModel):
    id: str
    screening_id: Optional[str] = None
    patient_id: Optional[str] = None
    event_type: str
    summary: str
    metadata: Dict[str, Any]
    created_at: datetime


class ScreeningReportResponse(BaseModel):
    report_id: str
    generated_at: datetime
    screening_id: str
    screening_reference: str
    screening_status: str
    screening_date: datetime
    patient: Dict[str, Any]
    consent: Dict[str, Any]
    images: List[Dict[str, Any]]
    latest_ai_run: Optional[AiRunResponse] = None
    explanations: Dict[str, Optional[AiExplanationResponse]] = Field(default_factory=dict)
    clinical_review: Optional[ClinicalReviewResponse] = None
    referrals: List[ReferralResponse]
    audit_trail: List[AuditLogResponse]
    clinical_safety_notice: str


class EyeComparisonResult(BaseModel):
    eye: str  # 'OD' | 'OS'
    has_previous_image: bool
    has_current_image: bool
    previous_grade: Optional[int] = None
    current_grade: Optional[int] = None
    previous_label: Optional[str] = None
    current_label: Optional[str] = None
    grade_difference: Optional[int] = None
    previous_probabilities: Dict[str, float] = Field(default_factory=dict)
    current_probabilities: Dict[str, float] = Field(default_factory=dict)
    probability_shifts: Dict[str, float] = Field(default_factory=dict)
    previous_vtdr_prob: Optional[float] = None
    current_vtdr_prob: Optional[float] = None
    vtdr_risk_shift: Optional[float] = None
    previous_gradable: bool = False
    current_gradable: bool = False
    has_previous_explanation: bool = False
    has_current_explanation: bool = False
    neutral_summary: str
    review_required_shift: bool = False


class ScreeningComparisonResponse(BaseModel):
    patient_id: str
    patient_name: str
    medical_record_number: str
    current_screening_id: str
    current_screening_reference: str
    current_screening_date: datetime
    previous_screening_id: str
    previous_screening_reference: str
    previous_screening_date: datetime
    days_interval: int
    is_directly_comparable: bool
    comparability_notes: List[str] = Field(default_factory=list)
    od_comparison: EyeComparisonResult
    os_comparison: EyeComparisonResult
    overall_comparison_summary: str
    clinical_safety_disclaimer: str


class PatientTimelineEvent(BaseModel):
    screening_id: str
    screening_reference: str
    screening_date: datetime
    status: str
    od_grade: Optional[int] = None
    os_grade: Optional[int] = None
    worst_grade: Optional[int] = None
    worst_label: Optional[str] = None
    referable_dr_risk: Optional[float] = None
    is_bilateral_complete: bool = False
    quality_status: str
    review_status: str
    reviewer_name: Optional[str] = None
    has_ai_run: bool = False
    report_id: Optional[str] = None
    trend_category: str
    trend_description: str


class PatientTimelineResponse(BaseModel):
    patient_id: str
    patient_name: str
    medical_record_number: str
    total_screenings: int
    events: List[PatientTimelineEvent]
    summary: str
    clinical_safety_notice: str


