from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255, description="Full legal name of the practitioner/user")
    email: EmailStr = Field(..., description="Valid professional or personal email address")
    password: str = Field(..., min_length=8, max_length=128, description="Account password (8-128 characters)")
    facility_name: Optional[str] = Field(None, max_length=255, description="Optional facility or clinical practice name")
    registration_number: Optional[str] = Field(None, max_length=100, description="Optional medical council / clinical registration number")


class UserLoginRequest(BaseModel):
    email: EmailStr = Field(..., description="Registered account email")
    password: str = Field(..., min_length=1, max_length=128, description="Account password")


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = Field(None, min_length=2, max_length=255)
    facility_name: Optional[str] = Field(None, max_length=255)
    registration_number: Optional[str] = Field(None, max_length=100)


class SafeUserResponse(BaseModel):
    id: str = Field(..., description="Unique user UUID")
    full_name: str
    email: str
    email_verified: bool
    is_active: bool
    facility_name: Optional[str] = None
    registration_number: Optional[str] = None
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class AuthSuccessResponse(BaseModel):
    success: bool = True
    message: str
    user: SafeUserResponse


class CSRFResponse(BaseModel):
    csrf_token: str
