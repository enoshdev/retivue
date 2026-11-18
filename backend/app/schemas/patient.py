from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.consent import ConsentCreate, ConsentResponse


class PatientCreate(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=255, description="Full legal or clinical name of the patient")
    patient_code: Optional[str] = Field(None, max_length=100, description="Optional local reference or clinic Medical Record Number (MRN)")
    date_of_birth: Optional[date] = Field(None, description="Patient date of birth (YYYY-MM-DD)")
    sex: Optional[str] = Field(None, max_length=32, description="Biological or administrative sex (male, female, other, unknown)")
    contact_number: Optional[str] = Field(None, max_length=50, description="Patient contact telephone number")
    diabetes_type: Optional[str] = Field(None, max_length=50, description="Type 1, Type 2, Gestational, Other, Unknown")
    diabetes_duration_years: Optional[int] = Field(None, ge=0, le=120, description="Duration of diagnosed diabetes in years")
    recent_hba1c: Optional[str] = Field(None, max_length=50, description="Recent glycemic control value, e.g. '7.4%'")
    notes: Optional[str] = Field(None, description="Clinical observations, ocular history, or encounter notes")
    initial_consent: Optional[ConsentCreate] = Field(None, description="Initial informed consent event captured at registration")


class PatientUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=255)
    patient_code: Optional[str] = Field(None, max_length=100)
    date_of_birth: Optional[date] = None
    sex: Optional[str] = Field(None, max_length=32)
    contact_number: Optional[str] = Field(None, max_length=50)
    diabetes_type: Optional[str] = Field(None, max_length=50)
    diabetes_duration_years: Optional[int] = Field(None, ge=0, le=120)
    recent_hba1c: Optional[str] = Field(None, max_length=50)
    notes: Optional[str] = None


class PatientResponse(BaseModel):
    id: str
    owner_user_id: str
    patient_code: Optional[str] = None
    full_name: str
    date_of_birth: Optional[date] = None
    sex: Optional[str] = None
    contact_number: Optional[str] = None
    diabetes_type: Optional[str] = None
    diabetes_duration_years: Optional[int] = None
    recent_hba1c: Optional[str] = None
    notes: Optional[str] = None
    is_archived: bool
    created_at: datetime
    updated_at: datetime
    screening_count: int = 0
    active_consent: Optional[ConsentResponse] = None

    model_config = ConfigDict(from_attributes=True)


class PatientListResponse(BaseModel):
    items: List[PatientResponse]
    total: int
    page: int
    page_size: int
    total_pages: int

