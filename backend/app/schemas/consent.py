from datetime import datetime
from typing import Optional, Literal
from pydantic import BaseModel, ConfigDict, Field


ConsentStatusType = Literal["pending", "granted", "declined", "revoked"]
CaptureMethodType = Literal["written_form", "verbal_recorded", "digital_acknowledgement", "direct_clinical_intake"]


class ConsentCreate(BaseModel):
    consent_type: str = Field("retinal_screening", max_length=100, description="Category of clinical consent")
    consent_status: ConsentStatusType = Field("granted", description="Granted, pending, declined, or revoked")
    capture_method: CaptureMethodType = Field("digital_acknowledgement", description="Method utilized to capture consent")
    notes: Optional[str] = Field(None, description="Optional clinical consent remarks or limitations")


class ConsentRevoke(BaseModel):
    notes: Optional[str] = Field(None, description="Clinical reason for revoking informed screening consent")


class ConsentResponse(BaseModel):
    id: str
    patient_id: str
    recorded_by_user_id: str
    consent_type: str
    consent_status: str
    capture_method: str
    captured_at: datetime
    revoked_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

