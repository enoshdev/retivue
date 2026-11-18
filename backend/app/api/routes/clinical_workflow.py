from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_csrf
from app.database.session import get_db
from app.models.user import User
from app.schemas.clinical_workflow import (
    AiModelRegistryItem,
    AiInferenceRequest,
    AiRunResponse,
    AiExplanationResponse,
    AiExplanationRegenerateRequest,
    ClinicalReviewCreate,
    ClinicalReviewResponse,
    ReferralCreate,
    ReferralStatusUpdate,
    ReferralResponse,
    AuditLogResponse,
    ScreeningReportResponse,
    ScreeningComparisonResponse,
    PatientTimelineResponse,
)
from app.services.ai_screening_service import AiScreeningService
from app.services.clinical_workflow_service import ClinicalWorkflowService
from app.storage import ImageStorageBackend, get_image_storage


router = APIRouter(tags=["Clinical Workflow & Decision Support"])


@router.get(
    "/workflow/ai-models",
    response_model=List[AiModelRegistryItem],
    status_code=status.HTTP_200_OK,
    summary="List Registered AI Models",
    description="Inspect frozen research checkpoint registry with SHA-256 integrity and provenance.",
)
async def list_ai_models(
    current_user: User = Depends(get_current_user),
):
    return AiScreeningService.get_registered_models()


@router.post(
    "/screenings/{screening_id}/ai-run",
    response_model=AiRunResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_csrf)],
    summary="Run AI Screening Inference",
    description="Executes quality-gated research AI analysis on bilateral retinal images.",
)
async def run_ai_screening(
    screening_id: str,
    payload: Optional[AiInferenceRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ImageStorageBackend = Depends(get_image_storage),
):
    model_key = payload.model_key if payload else None
    return await ClinicalWorkflowService.run_ai_analysis_for_screening(
        db=db,
        storage=storage,
        screening_id=screening_id,
        current_user=current_user,
        model_key=model_key,
    )


@router.get(
    "/screenings/{screening_id}/ai-runs",
    response_model=List[AiRunResponse],
    status_code=status.HTTP_200_OK,
    summary="List AI Screening Runs",
    description="Returns all historical research AI inference runs for the given encounter.",
)
async def list_ai_runs(
    screening_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ClinicalWorkflowService.list_ai_runs(
        db=db,
        screening_id=screening_id,
        owner_user_id=current_user.id,
    )


@router.get(
    "/screenings/{screening_id}/ai-runs/latest",
    response_model=Optional[AiRunResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Latest AI Run",
    description="Returns the most recent research AI screening run for the given encounter.",
)
async def get_latest_ai_run(
    screening_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ClinicalWorkflowService.get_latest_ai_run(
        db=db,
        screening_id=screening_id,
        owner_user_id=current_user.id,
    )


@router.get(
    "/screenings/{screening_id}/explanations/{eye}",
    response_model=AiExplanationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Grad-CAM Explanation Metadata",
    description="Returns genuine Grad-CAM explanation metadata and generation status for OD or OS.",
)
async def get_screening_explanation(
    screening_id: str,
    eye: str,
    target_class: Optional[int] = Query(None, ge=0, le=4, description="Target DR grade (0-4). Defaults to predicted grade."),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ImageStorageBackend = Depends(get_image_storage),
):
    return await ClinicalWorkflowService.get_explanation_for_screening(
        db=db,
        screening_id=screening_id,
        current_user=current_user,
        eye=eye,
        target_class=target_class,
        storage=storage,
    )


@router.get(
    "/screenings/{screening_id}/explanations/{eye}/heatmap",
    status_code=status.HTTP_200_OK,
    summary="Stream Grad-CAM Transparent Heatmap PNG",
    description="Streams genuine transparent Grad-CAM activation heatmap PNG aligned to original fundus geometry.",
)
async def stream_explanation_heatmap(
    screening_id: str,
    eye: str,
    target_class: Optional[int] = Query(None, ge=0, le=4, description="Target DR grade (0-4)."),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ImageStorageBackend = Depends(get_image_storage),
):
    return await ClinicalWorkflowService.stream_explanation_artifact(
        db=db,
        storage=storage,
        screening_id=screening_id,
        current_user=current_user,
        eye=eye,
        artifact_type="heatmap",
        target_class=target_class,
    )


@router.get(
    "/screenings/{screening_id}/explanations/{eye}/overlay",
    status_code=status.HTTP_200_OK,
    summary="Stream Grad-CAM Blended Overlay PNG",
    description="Streams composite fundus + Grad-CAM heatmap overlay PNG aligned to original fundus coordinates.",
)
async def stream_explanation_overlay(
    screening_id: str,
    eye: str,
    target_class: Optional[int] = Query(None, ge=0, le=4, description="Target DR grade (0-4)."),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ImageStorageBackend = Depends(get_image_storage),
):
    return await ClinicalWorkflowService.stream_explanation_artifact(
        db=db,
        storage=storage,
        screening_id=screening_id,
        current_user=current_user,
        eye=eye,
        artifact_type="overlay",
        target_class=target_class,
    )


@router.post(
    "/screenings/{screening_id}/explanations/{eye}/regenerate",
    response_model=AiExplanationResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_csrf)],
    summary="Regenerate or Switch Target Class Explanation",
    description="Generates or retrieves Grad-CAM for a specified target class (0-4), preventing duplicate computation if cached.",
)
async def regenerate_explanation(
    screening_id: str,
    eye: str,
    payload: Optional[AiExplanationRegenerateRequest] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ImageStorageBackend = Depends(get_image_storage),
):
    target_class = payload.target_class if payload else None
    return await ClinicalWorkflowService.regenerate_explanation_for_screening(
        db=db,
        storage=storage,
        screening_id=screening_id,
        current_user=current_user,
        eye=eye,
        target_class=target_class,
    )


@router.post(
    "/screenings/{screening_id}/review",
    response_model=ClinicalReviewResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
    summary="Sign Independent Clinical Review",
    description="Submits and digitally signs independent qualified professional clinical assessment.",
)
async def create_clinical_review(
    screening_id: str,
    payload: ClinicalReviewCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ClinicalWorkflowService.create_clinical_review(
        db=db,
        screening_id=screening_id,
        current_user=current_user,
        payload=payload,
    )


@router.get(
    "/screenings/{screening_id}/review",
    response_model=Optional[ClinicalReviewResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Signed Clinical Review",
    description="Retrieves the signed professional clinical review for this screening encounter.",
)
async def get_clinical_review(
    screening_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ClinicalWorkflowService.get_clinical_review(
        db=db,
        screening_id=screening_id,
        owner_user_id=current_user.id,
    )


@router.post(
    "/referrals",
    response_model=ReferralResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
    summary="Dispatch Specialist Referral",
    description="Creates a tertiary specialist referral following independent clinical sign-off.",
)
async def create_referral(
    payload: ReferralCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ClinicalWorkflowService.create_referral(
        db=db,
        current_user=current_user,
        payload=payload,
    )


@router.get(
    "/referrals",
    response_model=List[ReferralResponse],
    status_code=status.HTTP_200_OK,
    summary="List Referrals",
    description="Retrieves all specialist referrals dispatched by the authenticated owner.",
)
async def list_referrals(
    screening_id: Optional[str] = Query(None, description="Filter referrals by screening ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ClinicalWorkflowService.list_referrals(
        db=db,
        owner_user_id=current_user.id,
        screening_id=screening_id,
    )


@router.get(
    "/referrals/{referral_id}",
    response_model=ReferralResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Referral Details",
    description="Retrieves a single specialist referral by ID.",
)
async def get_referral(
    referral_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ClinicalWorkflowService.get_referral(
        db=db,
        referral_id=referral_id,
        owner_user_id=current_user.id,
    )


@router.patch(
    "/referrals/{referral_id}/status",
    response_model=ReferralResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(require_csrf)],
    summary="Update Referral Status",
    description="Updates specialist referral status and appointment scheduling notes.",
)
async def update_referral_status(
    referral_id: str,
    payload: ReferralStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ClinicalWorkflowService.update_referral_status(
        db=db,
        referral_id=referral_id,
        current_user=current_user,
        payload=payload,
    )


@router.get(
    "/screenings/{screening_id}/report",
    response_model=ScreeningReportResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Clinical Screening Report",
    description="Generates an integrated clinical screening report with audit provenance.",
)
async def get_screening_report(
    screening_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ClinicalWorkflowService.get_screening_report(
        db=db,
        screening_id=screening_id,
        current_user=current_user,
    )


@router.get(
    "/screenings/{screening_id}/audit",
    response_model=List[AuditLogResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Screening Audit Trail",
    description="Retrieves append-only chronological audit log entries for this screening encounter.",
)
async def get_screening_audit_trail(
    screening_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ClinicalWorkflowService.list_screening_audit_logs(
        db=db,
        screening_id=screening_id,
        owner_user_id=current_user.id,
    )


@router.get(
    "/screenings/{screening_id}/comparison",
    response_model=ScreeningComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Longitudinal Screening Comparison",
    description="Compares the specified encounter against a prior screening visit for the same patient.",
)
async def get_screening_comparison(
    screening_id: str,
    previous_screening_id: Optional[str] = Query(
        None,
        description="Optional prior screening ID to compare against. If omitted, the immediately preceding encounter is auto-selected.",
    ),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ClinicalWorkflowService.get_screening_comparison(
        db=db,
        current_screening_id=screening_id,
        current_user=current_user,
        previous_screening_id=previous_screening_id,
    )


@router.get(
    "/patients/{patient_id}/timeline",
    response_model=PatientTimelineResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Patient Screening Timeline",
    description="Retrieves chronological screening progression, bilateral grades, and review status across all visits.",
)
async def get_patient_timeline(
    patient_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    return await ClinicalWorkflowService.get_patient_timeline(
        db=db,
        patient_id=patient_id,
        current_user=current_user,
    )


@router.get(
    "/screenings/{screening_id}/report/pdf",
    status_code=status.HTTP_200_OK,
    summary="Download Official Screening PDF Report",
    description="Generates and streams a signed, formal ophthalmic screening PDF report.",
)
async def download_screening_pdf(
    screening_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    storage: ImageStorageBackend = Depends(get_image_storage),
):
    pdf_bytes = await ClinicalWorkflowService.generate_screening_pdf_report(
        db=db,
        storage=storage,
        screening_id=screening_id,
        current_user=current_user,
    )
    filename = f"retivue_screening_report_{screening_id[:8].upper()}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-cache, no-store, must-revalidate",
            "X-Content-Type-Options": "nosniff",
        },
    )
