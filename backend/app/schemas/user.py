from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr, ConfigDict


class OrganizationMembershipOut(BaseModel):
    id: str
    organization_id: str
    organization_name: Optional[str] = None
    role: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserOut(BaseModel):
    id: str
    email: EmailStr
    full_name: str
    primary_role: str  # independent_doctor, clinic_admin, vision_technician
    facility_name: Optional[str] = None
    registration_number: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime
    memberships: List[OrganizationMembershipOut] = []

    model_config = ConfigDict(from_attributes=True)
