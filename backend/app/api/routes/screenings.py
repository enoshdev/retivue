from typing import List, Optional
from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_csrf
from app.database.session import get_db
from app.models.user import User
from app.schemas.screening import (
    ScreeningCreate,
    ScreeningImageResponse,
    ScreeningImageUploadResponse,
    ScreeningListResponse,
    ScreeningResponse,
    ScreeningUpdate,
)
from app.services.screening_service import ScreeningService
from app.storage import ImageStorageBackend, get_image_storage

router = APIRouter(prefix="/screenings", tags=["Screening Management & Retinal Imaging"])


def _build_upload_response(
    img: ScreeningImageResponse,
    screening: ScreeningResponse,
) -> ScreeningImageUploadResponse:
    return ScreeningImageUploadResponse(
        **img.model_dump(),
        screening_status=screening.status,
        has_od_image=screening.has_od_image,
        has_os_image=screening.has_os_image,
        is_bilateral_complete=screening.is_bilateral_complete,
    )


@router.post(
    "",
    response_model=ScreeningResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Screening",
    description="Creates a new screening encounter linked strictly to the authenticated owner and an owned patient.",
)
async def create_screening(
    payload: ScreeningCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    return await ScreeningService.create_screening(
        db=db,
        owner_user_id=current_user.id,
        payload=payload,
    )


@router.get(
    "",
    response_model=ScreeningListResponse,
    status_code=status.HTTP_200_OK,
    summary="List Screenings",
    description="Lists paginated screening encounters scoped strictly to the authenticated owner.",
)
async def list_screenings(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    patient_id: Optional[str] = Query(None, description="Filter screenings by owned patient UUID"),
    status_filter: Optional[str] = Query(
        None,
        alias="status",
        pattern="^(draft|awaiting_images|images_incomplete|ready_for_quality_assessment|quality_failed_recapture_required|ai_completed_review_required|ai_completed_advisory|ai_failed_review_required|clinically_reviewed_signed|cancelled|archived)$",
        description="Filter by screening lifecycle state",
    ),
    include_archived: bool = Query(False, description="Include archived screenings"),
    sort_by: str = Query("created_at", pattern="^(created_at|updated_at|submitted_at)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ScreeningService.list_screenings(
        db=db,
        owner_user_id=current_user.id,
        page=page,
        page_size=page_size,
        patient_id=patient_id,
        status_filter=status_filter,
        include_archived=include_archived,
        sort_by=sort_by,
        sort_order=sort_order,
    )


@router.get(
    "/{screening_id}",
    response_model=ScreeningResponse,
    status_code=status.HTTP_200_OK,
    summary="Retrieve Screening",
    description="Retrieves screening encounter metadata and current OD/OS image upload statuses.",
)
async def get_screening(
    screening_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ScreeningService.get_screening(
        db=db,
        screening_id=screening_id,
        owner_user_id=current_user.id,
    )


@router.patch(
    "/{screening_id}",
    response_model=ScreeningResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Screening",
    description="Updates optional camera modality or clinical intake notes.",
)
async def update_screening(
    screening_id: str,
    payload: ScreeningUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    return await ScreeningService.update_screening(
        db=db,
        screening_id=screening_id,
        owner_user_id=current_user.id,
        payload=payload,
    )


@router.post(
    "/{screening_id}/images/{eye}",
    response_model=ScreeningImageUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload Eye Image (OD or OS)",
    description="Validates, checksums, and privately stores an original JPEG/PNG fundus image for OD or OS.",
)
async def upload_eye_image(
    screening_id: str,
    eye: str,
    file: UploadFile = File(...),
    replace: bool = Query(False, description="Allow controlled replacement if an image already exists"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ImageStorageBackend = Depends(get_image_storage),
    _csrf: None = Depends(require_csrf),
):
    img, screening = await ScreeningService.upload_or_replace_eye_image(
        db=db,
        storage=storage,
        screening_id=screening_id,
        owner_user_id=current_user.id,
        eye=eye,
        file=file,
        allow_replace=replace,
    )
    return _build_upload_response(img, screening)


@router.post(
    "/{screening_id}/images/{eye}/replace",
    response_model=ScreeningImageUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Replace Eye Image (Controlled Audit Replacement)",
    description="Preserves the previous original image in history and stores a new current original for OD or OS.",
)
@router.put(
    "/{screening_id}/images/{eye}",
    response_model=ScreeningImageUploadResponse,
    status_code=status.HTTP_200_OK,
    summary="Replace Eye Image via PUT",
    description="Controlled replacement endpoint preserving the prior image audit record and original bytes.",
)
async def replace_eye_image(
    screening_id: str,
    eye: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ImageStorageBackend = Depends(get_image_storage),
    _csrf: None = Depends(require_csrf),
):
    img, screening = await ScreeningService.upload_or_replace_eye_image(
        db=db,
        storage=storage,
        screening_id=screening_id,
        owner_user_id=current_user.id,
        eye=eye,
        file=file,
        allow_replace=True,
    )
    return _build_upload_response(img, screening)


@router.get(
    "/{screening_id}/images/{eye}",
    status_code=status.HTTP_200_OK,
    summary="Retrieve Current Eye Image",
    description="Authorizes owner and streams the current unmodified original image from private storage.",
)
async def retrieve_eye_image(
    screening_id: str,
    eye: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ImageStorageBackend = Depends(get_image_storage),
):
    image = await ScreeningService.get_current_eye_image_record(
        db=db,
        storage=storage,
        screening_id=screening_id,
        owner_user_id=current_user.id,
        eye=eye,
    )
    safe_name = image.original_filename or f"{eye.lower()}_fundus{image.file_extension}"
    headers = {
        "Content-Disposition": f'inline; filename="{safe_name}"',
        "Content-Length": str(image.file_size_bytes),
        "Cache-Control": "private, no-store, max-age=0",
        "X-Content-Type-Options": "nosniff",
        "ETag": f'"{image.sha256_checksum}"',
    }
    return StreamingResponse(
        storage.stream_chunks(image.storage_key),
        media_type=image.detected_media_type,
        headers=headers,
    )


@router.get(
    "/{screening_id}/images/{eye}/history",
    response_model=List[ScreeningImageResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Eye Image Replacement History",
    description="Returns chronological audit metadata for all uploaded/replaced images for this eye.",
)
async def get_eye_image_history(
    screening_id: str,
    eye: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ScreeningService.get_eye_image_history(
        db=db,
        screening_id=screening_id,
        owner_user_id=current_user.id,
        eye=eye,
    )


@router.post(
    "/{screening_id}/submit",
    response_model=ScreeningResponse,
    status_code=status.HTTP_200_OK,
    summary="Submit Screening for Quality Assessment",
    description=(
        "Verifies ownership, bilateral OD & OS storage integrity, and granted patient consent, "
        "then marks status as ready_for_quality_assessment (no ML execution in Phase 4)."
    ),
)
async def submit_screening(
    screening_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ImageStorageBackend = Depends(get_image_storage),
    _csrf: None = Depends(require_csrf),
):
    return await ScreeningService.submit_for_quality_assessment(
        db=db,
        storage=storage,
        screening_id=screening_id,
        owner_user_id=current_user.id,
    )


@router.post(
    "/{screening_id}/cancel",
    response_model=ScreeningResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel Screening",
)
async def cancel_screening(
    screening_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    return await ScreeningService.cancel_screening(
        db=db,
        screening_id=screening_id,
        owner_user_id=current_user.id,
    )


@router.post(
    "/{screening_id}/archive",
    response_model=ScreeningResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive Screening",
)
async def archive_screening(
    screening_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    return await ScreeningService.archive_screening(
        db=db,
        screening_id=screening_id,
        owner_user_id=current_user.id,
    )

