from datetime import datetime, date
from typing import List, Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


EyeLaterality = Literal["OD", "OS"]
ScreeningStatusLiteral = Literal[
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
]


class ScreeningCreate(BaseModel):
    patient_id: str = Field(..., min_length=1, max_length=36, description="Owned patient UUID")
    camera_model: Optional[str] = Field(None, max_length=255, description="Fundus camera hardware model")
    clinical_notes: Optional[str] = Field(None, max_length=2000, description="Optional encounter intake remarks")
    as_draft: bool = Field(False, description="Create in explicit draft state")

    model_config = ConfigDict(extra="ignore")


class ScreeningUpdate(BaseModel):
    camera_model: Optional[str] = Field(None, max_length=255)
    clinical_notes: Optional[str] = Field(None, max_length=2000)

    model_config = ConfigDict(extra="ignore")


class ScreeningImageResponse(BaseModel):
    """
    Safe metadata representation of a stored retinal image.
    Strictly omits internal storage_key and filesystem paths.
    """
    id: str
    screening_id: str
    eye: EyeLaterality
    original_filename: Optional[str] = None
    detected_media_type: str
    file_extension: str
    file_size_bytes: int
    image_width: int
    image_height: int
    sha256_checksum: str
    has_exif_metadata: bool
    uploaded_at: datetime
    upload_status: str
    is_current: bool
    replaced_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ScreeningImageUploadResponse(ScreeningImageResponse):
    screening_status: str
    has_od_image: bool
    has_os_image: bool
    is_bilateral_complete: bool


class PatientSummaryResponse(BaseModel):
    id: str
    patient_code: Optional[str] = None
    full_name: str
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None
    diabetes_type: Optional[str] = None
    recent_hba1c: Optional[str] = None
    consent_status: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ScreeningResponse(BaseModel):
    id: str
    owner_user_id: str
    patient_id: str
    screening_reference: str
    camera_model: Optional[str] = None
    clinical_notes: Optional[str] = None
    status: str
    has_od_image: bool
    has_os_image: bool
    is_bilateral_complete: bool
    od_image: Optional[ScreeningImageResponse] = None
    os_image: Optional[ScreeningImageResponse] = None
    patient: Optional[PatientSummaryResponse] = None
    created_at: datetime
    updated_at: datetime
    submitted_at: Optional[datetime] = None
    archived_at: Optional[datetime] = None


class ScreeningListResponse(BaseModel):
    items: List[ScreeningResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
