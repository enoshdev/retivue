from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import get_db
from app.api.deps import get_current_user, require_csrf
from app.models.user import User
from app.services.patient_service import PatientService
from app.schemas.patient import (
    PatientCreate,
    PatientUpdate,
    PatientResponse,
    PatientListResponse
)
from app.schemas.consent import (
    ConsentCreate,
    ConsentRevoke,
    ConsentResponse
)

router = APIRouter(prefix="/patients", tags=["Patient Management"])


@router.post(
    "",
    response_model=PatientResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Patient",
    description="Registers a new patient beneficiary record owned strictly by the authenticated clinician."
)
async def register_patient(
    payload: PatientCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf)
):
    """Registers patient record with authenticated user as owner."""
    return await PatientService.create_patient(
        db=db,
        owner_user_id=current_user.id,
        payload=payload
    )


@router.get(
    "",
    response_model=PatientListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Patients",
    description="Retrieves paginated patient directory strictly scoped to the authenticated clinician's account."
)
async def list_patients(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    query: Optional[str] = Query(None, description="Search term for name, MRN/patient code, or phone"),
    include_archived: bool = Query(False, description="Whether to include archived patient records"),
    sort_by: str = Query("created_at", pattern="^(created_at|name|updated_at)$", description="Field to sort by"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$", description="Sort direction"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Lists owned patients with search and pagination."""
    return await PatientService.list_patients(
        db=db,
        owner_user_id=current_user.id,
        page=page,
        page_size=page_size,
        search_query=query,
        include_archived=include_archived,
        sort_by=sort_by,
        sort_order=sort_order
    )


@router.get(
    "/{patient_id}",
    response_model=PatientResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Patient",
    description="Fetches individual patient details with active consent. Returns 404 if not found or unauthorized."
)
async def get_patient(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves patient record verifying owner isolation."""
    return await PatientService.get_patient(
        db=db,
        patient_id=patient_id,
        owner_user_id=current_user.id
    )


@router.patch(
    "/{patient_id}",
    response_model=PatientResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Patient",
    description="Updates permitted patient clinical and demographic fields. Verifies owner authorization."
)
async def update_patient(
    patient_id: str,
    payload: PatientUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf)
):
    """Updates permitted patient fields under ownership boundary."""
    return await PatientService.update_patient(
        db=db,
        patient_id=patient_id,
        owner_user_id=current_user.id,
        payload=payload
    )


@router.post(
    "/{patient_id}/archive",
    response_model=PatientResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive Patient",
    description="Soft-archives a patient record without destructive data loss."
)
async def archive_patient(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf)
):
    """Archives patient record while preserving historical screening records."""
    return await PatientService.archive_patient(
        db=db,
        patient_id=patient_id,
        owner_user_id=current_user.id
    )


@router.post(
    "/{patient_id}/unarchive",
    response_model=PatientResponse,
    status_code=status.HTTP_200_OK,
    summary="Unarchive Patient",
    description="Restores an archived patient record to active directory."
)
async def unarchive_patient(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf)
):
    """Restores an archived patient record."""
    return await PatientService.unarchive_patient(
        db=db,
        patient_id=patient_id,
        owner_user_id=current_user.id
    )


@router.post(
    "/{patient_id}/consent",
    response_model=ConsentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record Informed Consent",
    description="Records a new informed consent event in the audit trail for this patient."
)
async def record_consent(
    patient_id: str,
    payload: ConsentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf)
):
    """Appends an auditable informed consent entry for the patient."""
    return await PatientService.record_consent(
        db=db,
        patient_id=patient_id,
        owner_user_id=current_user.id,
        payload=payload
    )


@router.post(
    "/{patient_id}/consent/revoke",
    response_model=ConsentResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke Informed Consent",
    description="Appends a revocation event in the consent history audit trail."
)
async def revoke_consent(
    patient_id: str,
    payload: ConsentRevoke,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf)
):
    """Records consent revocation audit trail."""
    return await PatientService.revoke_consent(
        db=db,
        patient_id=patient_id,
        owner_user_id=current_user.id,
        payload=payload
    )


@router.get(
    "/{patient_id}/consent",
    response_model=List[ConsentResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Consent History",
    description="Retrieves the longitudinal audit trail of consent events for the patient."
)
async def get_consent_history(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Fetches full consent audit log for the patient."""
    return await PatientService.get_consent_history(
        db=db,
        patient_id=patient_id,
        owner_user_id=current_user.id
    )
