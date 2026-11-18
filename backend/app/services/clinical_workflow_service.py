import json
import secrets
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select, desc, asc
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import logger
from app.models.user import User
from app.models.patient import Patient
from app.models.screening import Screening
from app.models.clinical_review import ClinicalReview
from app.models.referral import Referral
from app.models.screening_ai import (
    ScreeningAiRun,
    ScreeningAiEyeResult,
    ScreeningAiExplanation,
)
from app.repositories.screening_repository import ScreeningRepository
from app.repositories.patient_repository import PatientRepository
from app.repositories.consent_repository import ConsentRepository
from app.repositories.clinical_workflow_repository import ClinicalWorkflowRepository
from app.storage.base import ImageStorageBackend
from app.schemas.clinical_workflow import (
    AiRunResponse,
    AiEyeResultResponse,
    AiExplanationResponse,
    ClinicalReviewCreate,
    ClinicalReviewResponse,
    ReferralCreate,
    ReferralStatusUpdate,
    ReferralResponse,
    AuditLogResponse,
    ScreeningReportResponse,
    EyeComparisonResult,
    ScreeningComparisonResponse,
    PatientTimelineEvent,
    PatientTimelineResponse,
)
from app.services.ai_screening_service import AiScreeningService
from app.services.pdf_report_service import PdfReportService
from ai.config import CLASS_INDEX_TO_LABEL


CLINICAL_SAFETY_NOTICE = (
    "NOTICE: This document contains decision-support findings generated during clinical screening encounters. "
    "All research AI metrics are auxiliary decision-support indicators and do NOT constitute autonomous diagnosis. "
    "Final clinical determinations must be made and formally signed by qualified, credentialed healthcare professionals."
)


def normalize_probabilities_dict(raw: Dict[str, Any]) -> Dict[str, float]:
    """
    Normalizes a probability dictionary into canonical key spaces:
    1. Numeric strings: '0', '1', '2', '3', '4'
    2. Canonical ICDR: 'class_0_no_dr', 'class_1_mild', 'class_2_moderate', 'class_3_severe', 'class_4_proliferative'
    3. Checkpoint labels: 'NO_DR', 'MILD_NPDR', 'MODERATE_NPDR', 'SEVERE_NPDR', 'PDR'
    """
    if not raw:
        return {}
    by_idx: Dict[int, float] = {}
    for k, v in raw.items():
        try:
            val = float(v)
        except (ValueError, TypeError):
            continue
        if str(k).isdigit() and 0 <= int(k) <= 4:
            by_idx[int(k)] = val
            continue
        lk = str(k).lower().replace("-", "_").replace(" ", "_")
        if "no_dr" in lk or "nodr" in lk or "class_0" in lk:
            by_idx[0] = val
        elif "mild" in lk or "class_1" in lk:
            by_idx[1] = val
        elif "moderate" in lk or "class_2" in lk:
            by_idx[2] = val
        elif "severe" in lk or "class_3" in lk:
            by_idx[3] = val
        elif "proliferative" in lk or "pdr" in lk or "class_4" in lk:
            by_idx[4] = val

    out: Dict[str, float] = {}
    for k, v in raw.items():
        try:
            out[k] = float(v)
        except (ValueError, TypeError):
            pass

    grade_specs = [
        (0, "class_0_no_dr", "NO_DR"),
        (1, "class_1_mild", "MILD_NPDR"),
        (2, "class_2_moderate", "MODERATE_NPDR"),
        (3, "class_3_severe", "SEVERE_NPDR"),
        (4, "class_4_proliferative", "PDR"),
    ]
    for idx, c_key, c_label in grade_specs:
        val = by_idx.get(idx, out.get(str(idx), out.get(c_key, out.get(c_label, 0.0))))
        out[str(idx)] = round(val, 6)
        out[c_key] = round(val, 6)
        out[c_label] = round(val, 6)

    return out


class ClinicalWorkflowService:
    """Orchestrates end-to-end clinical screening encounters, AI inference, sign-off, referrals, and audit trails."""

    @classmethod
    def _to_explanation_response(cls, exp: Optional[ScreeningAiExplanation]) -> Optional[AiExplanationResponse]:
        if not exp:
            return None
        return AiExplanationResponse(
            id=exp.id,
            screening_id=exp.screening_id,
            screening_image_id=exp.screening_image_id,
            ai_run_id=exp.ai_run_id,
            eye=exp.eye,
            target_class=exp.target_class,
            target_class_label=exp.target_class_label,
            is_default_target=exp.is_default_target,
            status=exp.status,
            explanation_text=exp.explanation_text,
            model_layer=exp.model_layer,
            image_sha256=exp.image_sha256,
            checkpoint_sha256=exp.checkpoint_sha256,
            has_heatmap=bool(exp.heatmap_storage_key),
            has_overlay=bool(exp.overlay_storage_key),
            created_at=exp.created_at,
        )

    @classmethod
    def _to_ai_eye_response(
        cls,
        eye: ScreeningAiEyeResult,
        explanation: Optional[ScreeningAiExplanation] = None,
    ) -> AiEyeResultResponse:
        return AiEyeResultResponse(
            id=eye.id,
            eye=eye.eye,
            screening_image_id=eye.screening_image_id,
            gradable=eye.gradable,
            quality_status=eye.quality_status,
            quality_reason=eye.quality_reason,
            quality_metrics=json.loads(eye.quality_metrics_json or "{}"),
            predicted_grade=eye.predicted_grade,
            predicted_label=eye.predicted_label,
            probabilities=normalize_probabilities_dict(json.loads(eye.probabilities_json or "{}")),
            confidence_max_prob=eye.confidence_max_prob,
            top2_margin=eye.top2_margin,
            normalized_entropy=eye.normalized_entropy,
            vtdr_prob_sum=eye.vtdr_prob_sum,
            uncertainty_review_required=eye.uncertainty_review_required,
            uncertainty_reasons=json.loads(eye.uncertainty_reasons_json or "[]"),
            high_risk_flagged=eye.high_risk_flagged,
            explanation=cls._to_explanation_response(explanation),
        )

    @classmethod
    def _to_ai_run_response(
        cls,
        run: ScreeningAiRun,
        explanations_by_eye: Optional[Dict[str, ScreeningAiExplanation]] = None,
    ) -> AiRunResponse:
        return AiRunResponse(
            id=run.id,
            screening_id=run.screening_id,
            model_key=run.model_key,
            model_version=run.model_version,
            architecture=run.architecture,
            checkpoint_sha256=run.checkpoint_sha256,
            checkpoint_epoch=run.checkpoint_epoch,
            preprocessing_config=json.loads(run.preprocessing_config_json or "{}"),
            overall_status=run.overall_status,
            overall_review_required=run.overall_review_required,
            overall_escalation_reasons=json.loads(run.overall_escalation_reasons_json or "[]"),
            higher_risk_eye=run.higher_risk_eye,
            highest_predicted_grade=run.highest_predicted_grade,
            highest_predicted_label=run.highest_predicted_label,
            research_disclaimer=run.research_disclaimer,
            calibration_warning=run.calibration_warning,
            error_message=run.error_message,
            execution_ms=run.execution_ms,
            inference_timestamp=run.inference_timestamp,
            eye_results=[
                cls._to_ai_eye_response(e, explanations_by_eye.get(e.eye) if explanations_by_eye else None)
                for e in run.eye_results
            ],
        )

    @classmethod
    def _to_clinical_review_response(cls, review: ClinicalReview) -> ClinicalReviewResponse:
        return ClinicalReviewResponse(
            id=review.id,
            screening_id=review.screening_id,
            reviewer_user_id=review.reviewer_user_id,
            reviewer_name_snapshot=review.reviewer_name_snapshot,
            reviewer_registration_number_snapshot=review.reviewer_registration_number_snapshot,
            linked_ai_run_id=review.linked_ai_run_id,
            od_confirmed_grade=review.od_confirmed_grade,
            od_confirmed_label=review.od_confirmed_label,
            os_confirmed_grade=review.os_confirmed_grade,
            os_confirmed_label=review.os_confirmed_label,
            worst_eye_confirmed_grade=review.worst_eye_confirmed_grade,
            worst_eye_confirmed_label=review.worst_eye_confirmed_label,
            ai_agreement_status=review.ai_agreement_status,
            override_rationale=review.override_rationale,
            clinical_findings=review.clinical_findings,
            follow_up_plan=review.follow_up_plan,
            recapture_required=review.recapture_required,
            is_signed=review.is_signed,
            signed_at=review.signed_at,
            created_at=review.created_at,
        )

    @classmethod
    def _to_referral_response(cls, ref: Referral) -> ReferralResponse:
        pat_name = ref.patient.full_name if ref.patient else None
        pat_mrn = ref.patient.patient_code if ref.patient else None
        return ReferralResponse(
            id=ref.id,
            referral_reference=ref.referral_reference,
            screening_id=ref.screening_id,
            clinical_review_id=ref.clinical_review_id,
            patient_id=ref.patient_id,
            patient_name=pat_name,
            patient_mrn=pat_mrn,
            urgency=ref.urgency,
            target_specialty=ref.target_specialty,
            target_facility=ref.target_facility,
            reason_summary=ref.reason_summary,
            clinical_summary=ref.clinical_summary,
            status=ref.status,
            appointment_notes=ref.appointment_notes,
            dispatched_at=ref.dispatched_at,
            updated_at=ref.updated_at,
        )

    @classmethod
    async def run_ai_analysis_for_screening(
        cls,
        db: AsyncSession,
        storage: ImageStorageBackend,
        screening_id: str,
        current_user: User,
        model_key: Optional[str] = None,
    ) -> AiRunResponse:
        # 1. Ownership & existence check
        screening = await ScreeningRepository.get_by_id_and_owner(db, screening_id, current_user.id)
        if not screening:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening record not found.")

        # 2. Block if clinical review already signed
        existing_review = await ClinicalWorkflowRepository.get_clinical_review_for_screening(
            db, screening.id, current_user.id
        )
        if existing_review and existing_review.is_signed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A signed clinical review already exists for this screening. AI inference cannot alter signed clinical records.",
            )

        if screening.status in ("cancelled", "archived"):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot run AI analysis on screening in '{screening.status}' state.",
            )

        # 3. Verify patient ownership and informed consent status
        patient = await PatientRepository.get_by_id_and_owner(db, screening.patient_id, current_user.id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient record not found.")

        latest_consent = await ConsentRepository.get_latest_by_patient(
            db=db,
            patient_id=patient.id,
            consent_type="retinal_screening",
        )
        if not latest_consent or latest_consent.consent_status != "granted":
            c_status = latest_consent.consent_status if latest_consent else "missing"
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Patient informed consent is '{c_status}'. Valid granted consent is strictly required for AI analysis.",
            )

        # 4. Verify bilateral images exist in DB and storage
        od_img = await ScreeningRepository.get_current_image(db, screening.id, current_user.id, "OD")
        os_img = await ScreeningRepository.get_current_image(db, screening.id, current_user.id, "OS")
        if not od_img or not os_img:
            missing = []
            if not od_img:
                missing.append("OD (Right Eye)")
            if not os_img:
                missing.append("OS (Left Eye)")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Bilateral images required. Missing: {', '.join(missing)}.",
            )

        # Read original bytes from private storage
        try:
            od_bytes = await storage.read_bytes(od_img.storage_key)
            os_bytes = await storage.read_bytes(os_img.storage_key)
        except Exception as exc:
            logger.error(f"Failed to read images from storage for screening {screening.id}: {exc}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to load retinal images from secure storage.",
            )

        # 5. Execute AI screening service
        try:
            ai_run, eye_results, cam_dict = await AiScreeningService.run_ai_screening(
                screening_id=screening.id,
                owner_user_id=current_user.id,
                triggered_by_user_id=current_user.id,
                od_image_id=od_img.id,
                od_bytes=od_bytes,
                os_image_id=os_img.id,
                os_bytes=os_bytes,
                model_key=model_key,
            )
        except Exception as exc:
            logger.error(f"AI screening error for screening {screening.id}: {exc}")
            await ClinicalWorkflowRepository.append_audit_log(
                db=db,
                owner_user_id=current_user.id,
                actor_user_id=current_user.id,
                screening_id=screening.id,
                patient_id=patient.id,
                event_type="AI_SCREENING_FAILED",
                summary=f"AI screening execution failed: {exc.__class__.__name__}",
                metadata={"error": str(exc)},
            )
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AI screening inference encountered an error: {str(exc)}",
            )

        # 6. Save AI run records
        persisted_run = await ClinicalWorkflowRepository.create_ai_run(db, ai_run, eye_results)

        # 6b. Persist Grad-CAM explainability artifacts and database records
        explanations_map: Dict[str, ScreeningAiExplanation] = {}
        for eye_label, img_record in [("OD", od_img), ("OS", os_img)]:
            cam_data = cam_dict.get(eye_label, {})
            heatmap_key: Optional[str] = None
            overlay_key: Optional[str] = None

            if cam_data.get("heatmap_bytes"):
                heatmap_key = f"screenings/{screening.id}/explanations/{eye_label.lower()}_class{cam_data['target_class']}_heatmap_{uuid.uuid4().hex[:8]}.png"
                await storage.save_bytes(heatmap_key, cam_data["heatmap_bytes"], "image/png")

            if cam_data.get("overlay_bytes"):
                overlay_key = f"screenings/{screening.id}/explanations/{eye_label.lower()}_class{cam_data['target_class']}_overlay_{uuid.uuid4().hex[:8]}.png"
                await storage.save_bytes(overlay_key, cam_data["overlay_bytes"], "image/png")

            cached = await ClinicalWorkflowRepository.get_cached_explanation(
                db=db,
                screening_image_id=img_record.id,
                checkpoint_sha256=persisted_run.checkpoint_sha256,
                target_class=cam_data.get("target_class", 0),
            )
            if cached:
                cached.ai_run_id = persisted_run.id
                cached.is_default_target = True
                cached.explanation_text = cam_data.get("explanation_text", cached.explanation_text)
                if heatmap_key:
                    cached.heatmap_storage_key = heatmap_key
                if overlay_key:
                    cached.overlay_storage_key = overlay_key
                explanations_map[eye_label] = cached
                await db.flush()
            else:
                exp = ScreeningAiExplanation(
                    screening_id=screening.id,
                    screening_image_id=img_record.id,
                    ai_run_id=persisted_run.id,
                    owner_user_id=current_user.id,
                    eye=eye_label,
                    target_class=cam_data.get("target_class", 0),
                    target_class_label=cam_data.get("target_class_label", "No_DR"),
                    is_default_target=True,
                    status=cam_data.get("status", "completed"),
                    explanation_text=cam_data.get("explanation_text", "Explanation generated."),
                    model_layer=cam_data.get("model_layer", "features.8"),
                    image_sha256=img_record.sha256_checksum,
                    checkpoint_sha256=persisted_run.checkpoint_sha256,
                    heatmap_storage_key=heatmap_key,
                    overlay_storage_key=overlay_key,
                )
                saved_exp = await ClinicalWorkflowRepository.save_explanation(db, exp)
                explanations_map[eye_label] = saved_exp

        # 7. Update screening status according to quality and uncertainty
        if persisted_run.overall_status == "quality_failed":
            new_status = "quality_failed_recapture_required"
        elif persisted_run.overall_review_required:
            new_status = "ai_completed_review_required"
        else:
            new_status = "ai_completed_advisory"

        await ScreeningRepository.update_status(db, screening, new_status)

        # 8. Record audit trail
        await ClinicalWorkflowRepository.append_audit_log(
            db=db,
            owner_user_id=current_user.id,
            actor_user_id=current_user.id,
            screening_id=screening.id,
            patient_id=patient.id,
            event_type="AI_SCREENING_EXECUTED",
            summary=(
                f"AI screening executed using {persisted_run.model_key} "
                f"(Status: {persisted_run.overall_status}, Review Required: {persisted_run.overall_review_required})"
            ),
            metadata={
                "ai_run_id": persisted_run.id,
                "model_key": persisted_run.model_key,
                "model_version": persisted_run.model_version,
                "checkpoint_sha256": persisted_run.checkpoint_sha256,
                "overall_status": persisted_run.overall_status,
                "overall_review_required": persisted_run.overall_review_required,
                "higher_risk_eye": persisted_run.higher_risk_eye,
                "highest_predicted_grade": persisted_run.highest_predicted_grade,
                "new_screening_status": new_status,
                "explanations_generated": {eye: exp.status for eye, exp in explanations_map.items()},
            },
        )
        await db.commit()
        return cls._to_ai_run_response(persisted_run, explanations_map)

    @classmethod
    async def get_latest_ai_run(
        cls,
        db: AsyncSession,
        screening_id: str,
        owner_user_id: str,
    ) -> Optional[AiRunResponse]:
        run = await ClinicalWorkflowRepository.get_latest_ai_run_for_screening(db, screening_id, owner_user_id)
        if not run:
            return None
        all_exps = await ClinicalWorkflowRepository.list_explanations_for_screening(db, screening_id, owner_user_id)
        exps_by_eye = {exp.eye: exp for exp in all_exps if exp.is_default_target}
        return cls._to_ai_run_response(run, exps_by_eye)

    @classmethod
    async def list_ai_runs(
        cls,
        db: AsyncSession,
        screening_id: str,
        owner_user_id: str,
    ) -> List[AiRunResponse]:
        runs = await ClinicalWorkflowRepository.list_ai_runs_for_screening(db, screening_id, owner_user_id)
        all_exps = await ClinicalWorkflowRepository.list_explanations_for_screening(db, screening_id, owner_user_id)
        exps_by_eye = {exp.eye: exp for exp in all_exps if exp.is_default_target}
        return [cls._to_ai_run_response(r, exps_by_eye) for r in runs]

    @classmethod
    async def get_explanation_for_screening(
        cls,
        db: AsyncSession,
        screening_id: str,
        current_user: User,
        eye: str,
        target_class: Optional[int] = None,
        storage: Optional[ImageStorageBackend] = None,
    ) -> AiExplanationResponse:
        validated_eye = eye.strip().upper()
        if validated_eye not in ("OD", "OS"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Eye must be 'OD' or 'OS'.")

        screening = await ScreeningRepository.get_by_id_and_owner(db, screening_id, current_user.id)
        if not screening:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening record not found.")

        exp = await ClinicalWorkflowRepository.get_explanation_by_eye(
            db=db,
            screening_id=screening.id,
            owner_user_id=current_user.id,
            eye=validated_eye,
            target_class=target_class,
        )
        if not exp and storage is not None:
            # Fallback: check if an image exists and dynamically generate the explanation on-demand
            img_record = await ScreeningRepository.get_current_image(db, screening.id, current_user.id, validated_eye)
            if img_record:
                try:
                    return await cls.regenerate_explanation_for_screening(
                        db=db,
                        storage=storage,
                        screening_id=screening.id,
                        current_user=current_user,
                        eye=validated_eye,
                        target_class=target_class,
                    )
                except Exception as auto_exc:
                    logger.warning(f"On-demand Grad-CAM generation fallback failed: {auto_exc}")

        if not exp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No explanation found for {validated_eye}" + (f" class {target_class}" if target_class is not None else "") + ".",
            )
        return cls._to_explanation_response(exp)

    @classmethod
    async def stream_explanation_artifact(
        cls,
        db: AsyncSession,
        storage: ImageStorageBackend,
        screening_id: str,
        current_user: User,
        eye: str,
        artifact_type: str,
        target_class: Optional[int] = None,
    ) -> StreamingResponse:
        validated_eye = eye.strip().upper()
        if validated_eye not in ("OD", "OS"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Eye must be 'OD' or 'OS'.")

        screening = await ScreeningRepository.get_by_id_and_owner(db, screening_id, current_user.id)
        if not screening:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening record not found.")

        exp = await ClinicalWorkflowRepository.get_explanation_by_eye(
            db=db,
            screening_id=screening.id,
            owner_user_id=current_user.id,
            eye=validated_eye,
            target_class=target_class,
        )
        if not exp:
            img_record = await ScreeningRepository.get_current_image(db, screening.id, current_user.id, validated_eye)
            if img_record:
                try:
                    await cls.regenerate_explanation_for_screening(
                        db=db,
                        storage=storage,
                        screening_id=screening.id,
                        current_user=current_user,
                        eye=validated_eye,
                        target_class=target_class,
                    )
                    exp = await ClinicalWorkflowRepository.get_explanation_by_eye(
                        db=db,
                        screening_id=screening.id,
                        owner_user_id=current_user.id,
                        eye=validated_eye,
                        target_class=target_class,
                    )
                except Exception as auto_exc:
                    logger.warning(f"Auto-generation during stream failed: {auto_exc}")

        if not exp:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Explanation artifact record not found.")

        storage_key = exp.heatmap_storage_key if artifact_type == "heatmap" else exp.overlay_storage_key
        if not storage_key or not await storage.exists(storage_key):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Explanation {artifact_type} image file not found.")

        filename = f"{validated_eye.lower()}_class{exp.target_class}_{artifact_type}.png"
        headers = {
            "Content-Disposition": f'inline; filename="{filename}"',
            "Cache-Control": "private, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        }
        return StreamingResponse(
            storage.stream_chunks(storage_key),
            media_type="image/png",
            headers=headers,
        )

    @classmethod
    async def regenerate_explanation_for_screening(
        cls,
        db: AsyncSession,
        storage: ImageStorageBackend,
        screening_id: str,
        current_user: User,
        eye: str,
        target_class: Optional[int] = None,
    ) -> AiExplanationResponse:
        validated_eye = eye.strip().upper()
        if validated_eye not in ("OD", "OS"):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Eye must be 'OD' or 'OS'.")

        screening = await ScreeningRepository.get_by_id_and_owner(db, screening_id, current_user.id)
        if not screening:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening record not found.")

        img_record = await ScreeningRepository.get_current_image(db, screening.id, current_user.id, validated_eye)
        if not img_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No image uploaded for {validated_eye}.")

        latest_run = await ClinicalWorkflowRepository.get_latest_ai_run_for_screening(db, screening.id, current_user.id)
        ckpt_sha = latest_run.checkpoint_sha256 if latest_run else "a94c4d0e2ac2e5200dabe6da122337f7a4191557dba5c02c85e52014b168686b"
        model_k = latest_run.model_key if latest_run else None

        # Resolve target class: default to latest eye prediction or 0
        resolved_target = target_class
        if resolved_target is None:
            if latest_run:
                eye_r = next((e for e in latest_run.eye_results if e.eye == validated_eye), None)
                resolved_target = eye_r.predicted_grade if eye_r and eye_r.predicted_grade is not None else 0
            else:
                resolved_target = 0

        # Check cache
        cached = await ClinicalWorkflowRepository.get_cached_explanation(
            db=db,
            screening_image_id=img_record.id,
            checkpoint_sha256=ckpt_sha,
            target_class=resolved_target,
        )
        if cached and cached.status == "completed" and cached.overlay_storage_key and await storage.exists(cached.overlay_storage_key):
            return cls._to_explanation_response(cached)

        # Read original image bytes
        raw_bytes = await storage.read_bytes(img_record.storage_key)

        # Run Grad-CAM generation
        cam_data = await AiScreeningService.generate_explanation_for_image_bytes(
            raw_bytes=raw_bytes,
            target_class=resolved_target,
            model_key=model_k,
        )

        heatmap_key: Optional[str] = None
        overlay_key: Optional[str] = None
        if cam_data.get("heatmap_bytes"):
            heatmap_key = f"screenings/{screening.id}/explanations/{validated_eye.lower()}_class{resolved_target}_heatmap_{uuid.uuid4().hex[:8]}.png"
            await storage.save_bytes(heatmap_key, cam_data["heatmap_bytes"], "image/png")

        if cam_data.get("overlay_bytes"):
            overlay_key = f"screenings/{screening.id}/explanations/{validated_eye.lower()}_class{resolved_target}_overlay_{uuid.uuid4().hex[:8]}.png"
            await storage.save_bytes(overlay_key, cam_data["overlay_bytes"], "image/png")

        is_default = (latest_run is not None and any(e.eye == validated_eye and e.predicted_grade == resolved_target for e in latest_run.eye_results))
        if cached:
            cached.status = cam_data.get("status", "completed")
            cached.explanation_text = cam_data.get("explanation_text", "")
            if heatmap_key:
                cached.heatmap_storage_key = heatmap_key
            if overlay_key:
                cached.overlay_storage_key = overlay_key
            await db.flush()
            exp_record = cached
        else:
            exp_record = ScreeningAiExplanation(
                screening_id=screening.id,
                screening_image_id=img_record.id,
                ai_run_id=latest_run.id if latest_run else "",
                owner_user_id=current_user.id,
                eye=validated_eye,
                target_class=resolved_target,
                target_class_label=cam_data.get("target_class_label", f"Grade_{resolved_target}"),
                is_default_target=is_default,
                status=cam_data.get("status", "completed"),
                explanation_text=cam_data.get("explanation_text", ""),
                model_layer=cam_data.get("model_layer", "features.8"),
                image_sha256=img_record.sha256_checksum,
                checkpoint_sha256=ckpt_sha,
                heatmap_storage_key=heatmap_key,
                overlay_storage_key=overlay_key,
            )
            exp_record = await ClinicalWorkflowRepository.save_explanation(db, exp_record)

        await ClinicalWorkflowRepository.append_audit_log(
            db=db,
            owner_user_id=current_user.id,
            actor_user_id=current_user.id,
            screening_id=screening.id,
            patient_id=screening.patient_id,
            event_type="EXPLANATION_REGENERATED",
            summary=f"Grad-CAM explanation generated for {validated_eye} target class {resolved_target} ({exp_record.target_class_label}).",
            metadata={
                "eye": validated_eye,
                "target_class": resolved_target,
                "status": exp_record.status,
            },
        )
        await db.commit()
        return cls._to_explanation_response(exp_record)

    @classmethod
    async def create_clinical_review(
        cls,
        db: AsyncSession,
        screening_id: str,
        current_user: User,
        payload: ClinicalReviewCreate,
    ) -> ClinicalReviewResponse:
        # 1. Check ownership & existence
        screening = await ScreeningRepository.get_by_id_and_owner(db, screening_id, current_user.id)
        if not screening:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening record not found.")

        # 2. Strict authorization: practitioner registration credential required
        reg_num = (current_user.registration_number or "").strip()
        if len(reg_num) < 3:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only registered healthcare professionals with a valid medical registration number may sign clinical assessments.",
            )

        # 3. Check for existing review
        existing = await ClinicalWorkflowRepository.get_clinical_review_for_screening(db, screening.id, current_user.id)
        if existing and existing.is_signed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A signed clinical assessment already exists for this encounter and cannot be overwritten.",
            )

        # 4. Resolve labels and worst-eye findings
        od_label = CLASS_INDEX_TO_LABEL.get(payload.od_confirmed_grade) if payload.od_confirmed_grade is not None else None
        os_label = CLASS_INDEX_TO_LABEL.get(payload.os_confirmed_grade) if payload.os_confirmed_grade is not None else None

        worst_grade: Optional[int] = None
        worst_label: Optional[str] = None
        if payload.od_confirmed_grade is not None and payload.os_confirmed_grade is not None:
            worst_grade = max(payload.od_confirmed_grade, payload.os_confirmed_grade)
            worst_label = CLASS_INDEX_TO_LABEL.get(worst_grade)
        elif payload.od_confirmed_grade is not None:
            worst_grade = payload.od_confirmed_grade
            worst_label = od_label
        elif payload.os_confirmed_grade is not None:
            worst_grade = payload.os_confirmed_grade
            worst_label = os_label

        latest_run = await ClinicalWorkflowRepository.get_latest_ai_run_for_screening(db, screening.id, current_user.id)

        review = ClinicalReview(
            screening_id=screening.id,
            owner_user_id=current_user.id,
            reviewer_user_id=current_user.id,
            linked_ai_run_id=latest_run.id if latest_run else None,
            reviewer_name_snapshot=current_user.full_name,
            reviewer_registration_number_snapshot=reg_num,
            od_confirmed_grade=payload.od_confirmed_grade,
            od_confirmed_label=od_label,
            os_confirmed_grade=payload.os_confirmed_grade,
            os_confirmed_label=os_label,
            worst_eye_confirmed_grade=worst_grade,
            worst_eye_confirmed_label=worst_label,
            ai_agreement_status=payload.ai_agreement_status,
            override_rationale=payload.override_rationale,
            clinical_findings=payload.clinical_findings,
            follow_up_plan=payload.follow_up_plan,
            recapture_required=payload.recapture_required,
            is_signed=True,
            signed_at=datetime.now(timezone.utc),
        )

        persisted = await ClinicalWorkflowRepository.create_clinical_review(db, review)
        await ScreeningRepository.update_status(db, screening, "clinically_reviewed_signed")

        # Record audit log
        await ClinicalWorkflowRepository.append_audit_log(
            db=db,
            owner_user_id=current_user.id,
            actor_user_id=current_user.id,
            screening_id=screening.id,
            patient_id=screening.patient_id,
            event_type="CLINICAL_REVIEW_SIGNED",
            summary=(
                f"Independent clinical review signed by {current_user.full_name} "
                f"({reg_num}). Agreement: {payload.ai_agreement_status}. Worst grade: {worst_grade}."
            ),
            metadata={
                "clinical_review_id": persisted.id,
                "reviewer_name": current_user.full_name,
                "registration_number": reg_num,
                "ai_agreement_status": payload.ai_agreement_status,
                "worst_eye_confirmed_grade": worst_grade,
                "recapture_required": payload.recapture_required,
            },
        )
        await db.commit()
        return cls._to_clinical_review_response(persisted)

    @classmethod
    async def get_clinical_review(
        cls,
        db: AsyncSession,
        screening_id: str,
        owner_user_id: str,
    ) -> Optional[ClinicalReviewResponse]:
        review = await ClinicalWorkflowRepository.get_clinical_review_for_screening(db, screening_id, owner_user_id)
        return cls._to_clinical_review_response(review) if review else None

    @classmethod
    async def create_referral(
        cls,
        db: AsyncSession,
        current_user: User,
        payload: ReferralCreate,
    ) -> ReferralResponse:
        screening = await ScreeningRepository.get_by_id_and_owner(db, payload.screening_id, current_user.id)
        if not screening:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening record not found.")

        # Require a signed clinical review before dispatching referral
        review = await ClinicalWorkflowRepository.get_clinical_review_for_screening(db, screening.id, current_user.id)
        if not review or not review.is_signed:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A specialist referral cannot be dispatched without a signed independent clinical review.",
            )

        ref_code = f"REF-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(3).upper()}"

        referral = Referral(
            referral_reference=ref_code,
            screening_id=screening.id,
            clinical_review_id=review.id,
            patient_id=screening.patient_id,
            owner_user_id=current_user.id,
            created_by_user_id=current_user.id,
            urgency=payload.urgency,
            target_specialty=payload.target_specialty,
            target_facility=payload.target_facility,
            reason_summary=payload.reason_summary,
            clinical_summary=payload.clinical_summary,
            status="DISPATCHED",
        )

        persisted = await ClinicalWorkflowRepository.create_referral(db, referral)

        await ClinicalWorkflowRepository.append_audit_log(
            db=db,
            owner_user_id=current_user.id,
            actor_user_id=current_user.id,
            screening_id=screening.id,
            patient_id=screening.patient_id,
            event_type="SPECIALIST_REFERRAL_DISPATCHED",
            summary=(
                f"Specialist referral {ref_code} ({payload.urgency}) dispatched to "
                f"{payload.target_facility} - {payload.target_specialty}."
            ),
            metadata={
                "referral_id": persisted.id,
                "referral_reference": ref_code,
                "urgency": payload.urgency,
                "target_facility": payload.target_facility,
                "target_specialty": payload.target_specialty,
            },
        )
        await db.commit()
        return cls._to_referral_response(persisted)

    @classmethod
    async def list_referrals(
        cls,
        db: AsyncSession,
        owner_user_id: str,
        screening_id: Optional[str] = None,
    ) -> List[ReferralResponse]:
        referrals = await ClinicalWorkflowRepository.list_referrals_for_owner(db, owner_user_id, screening_id)
        return [cls._to_referral_response(r) for r in referrals]

    @classmethod
    async def get_referral(
        cls,
        db: AsyncSession,
        referral_id: str,
        owner_user_id: str,
    ) -> ReferralResponse:
        ref = await ClinicalWorkflowRepository.get_referral_by_id(db, referral_id, owner_user_id)
        if not ref:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral record not found.")
        return cls._to_referral_response(ref)

    @classmethod
    async def update_referral_status(
        cls,
        db: AsyncSession,
        referral_id: str,
        current_user: User,
        payload: ReferralStatusUpdate,
    ) -> ReferralResponse:
        ref = await ClinicalWorkflowRepository.get_referral_by_id(db, referral_id, current_user.id)
        if not ref:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Referral record not found.")

        old_status = ref.status
        ref.status = payload.status
        if payload.appointment_notes is not None:
            ref.appointment_notes = payload.appointment_notes
        ref.updated_at = datetime.now(timezone.utc)
        await db.flush()

        await ClinicalWorkflowRepository.append_audit_log(
            db=db,
            owner_user_id=current_user.id,
            actor_user_id=current_user.id,
            screening_id=ref.screening_id,
            patient_id=ref.patient_id,
            event_type="REFERRAL_STATUS_UPDATED",
            summary=f"Referral {ref.referral_reference} status changed from {old_status} to {payload.status}.",
            metadata={
                "referral_id": ref.id,
                "old_status": old_status,
                "new_status": payload.status,
            },
        )
        await db.commit()
        await db.refresh(ref)
        return cls._to_referral_response(ref)

    @classmethod
    async def list_screening_audit_logs(
        cls,
        db: AsyncSession,
        screening_id: str,
        owner_user_id: str,
    ) -> List[AuditLogResponse]:
        screening = await ScreeningRepository.get_by_id_and_owner(db, screening_id, owner_user_id)
        if not screening:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening record not found.")
        logs = await ClinicalWorkflowRepository.list_audit_logs_for_screening(db, screening_id, owner_user_id)
        return [
            AuditLogResponse(
                id=log.id,
                screening_id=log.screening_id,
                patient_id=log.patient_id,
                event_type=log.event_type,
                summary=log.summary,
                metadata=json.loads(log.metadata_json or "{}"),
                created_at=log.created_at,
            )
            for log in logs
        ]

    @classmethod
    async def get_screening_report(
        cls,
        db: AsyncSession,
        screening_id: str,
        current_user: User,
    ) -> ScreeningReportResponse:
        screening = await ScreeningRepository.get_by_id_and_owner(db, screening_id, current_user.id)
        if not screening:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening record not found.")

        patient = await PatientRepository.get_by_id_and_owner(db, screening.patient_id, current_user.id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient record not found.")

        latest_consent = await ConsentRepository.get_latest_by_patient(
            db=db,
            patient_id=patient.id,
            consent_type="retinal_screening",
        )

        latest_ai_run = await cls.get_latest_ai_run(db, screening.id, current_user.id)
        od_exp = await ClinicalWorkflowRepository.get_explanation_by_eye(db, screening.id, current_user.id, "OD")
        os_exp = await ClinicalWorkflowRepository.get_explanation_by_eye(db, screening.id, current_user.id, "OS")
        explanations_dict = {
            "OD": cls._to_explanation_response(od_exp),
            "OS": cls._to_explanation_response(os_exp),
        }
        clinical_review = await cls.get_clinical_review(db, screening.id, current_user.id)
        referrals = await cls.list_referrals(db, current_user.id, screening_id=screening.id)
        audit_trail = await cls.list_screening_audit_logs(db, screening.id, current_user.id)

        # Record report access event
        await ClinicalWorkflowRepository.append_audit_log(
            db=db,
            owner_user_id=current_user.id,
            actor_user_id=current_user.id,
            screening_id=screening.id,
            patient_id=patient.id,
            event_type="SCREENING_REPORT_ACCESSED",
            summary=f"Clinical screening report accessed by {current_user.full_name}.",
            metadata={"screening_id": screening.id},
        )
        await db.commit()

        images_info = [
            {
                "id": img.id,
                "eye": img.eye,
                "file_size_bytes": img.file_size_bytes,
                "width": img.image_width,
                "height": img.image_height,
                "checksum": img.sha256_checksum,
                "uploaded_at": img.uploaded_at.isoformat(),
                "is_current": img.is_current,
            }
            for img in screening.images
        ]

        return ScreeningReportResponse(
            report_id=f"RPT-{screening.id[:8].upper()}-{datetime.now(timezone.utc).strftime('%Y%m%d')}",
            generated_at=datetime.now(timezone.utc),
            screening_id=screening.id,
            screening_reference=f"SCR-{screening.id[:8].upper()}",
            screening_status=screening.status,
            screening_date=screening.created_at,
            patient={
                "id": patient.id,
                "full_name": patient.full_name,
                "medical_record_number": patient.patient_code or "",
                "date_of_birth": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
                "gender": patient.sex,
                "diabetes_type": patient.diabetes_type,
            },
            consent={
                "status": latest_consent.consent_status if latest_consent else "missing",
                "obtained_at": latest_consent.captured_at.isoformat() if latest_consent else None,
                "capture_method": latest_consent.capture_method if latest_consent else None,
            },
            images=images_info,
            latest_ai_run=latest_ai_run,
            explanations=explanations_dict,
            clinical_review=clinical_review,
            referrals=referrals,
            audit_trail=audit_trail,
            clinical_safety_notice=CLINICAL_SAFETY_NOTICE,
        )

    @classmethod
    def _build_eye_comparison(
        cls,
        eye: str,
        curr_img: Any,
        prev_img: Any,
        curr_res: Optional[AiEyeResultResponse],
        prev_res: Optional[AiEyeResultResponse],
        curr_expl: Optional[ScreeningAiExplanation],
        prev_expl: Optional[ScreeningAiExplanation],
    ) -> EyeComparisonResult:
        has_prev_img = prev_img is not None
        has_curr_img = curr_img is not None

        prev_grade = prev_res.predicted_grade if prev_res and prev_res.predicted_grade is not None else None
        curr_grade = curr_res.predicted_grade if curr_res and curr_res.predicted_grade is not None else None
        prev_label = CLASS_INDEX_TO_LABEL.get(prev_grade) if prev_grade is not None else None
        curr_label = CLASS_INDEX_TO_LABEL.get(curr_grade) if curr_grade is not None else None

        grade_diff = None
        if prev_grade is not None and curr_grade is not None:
            grade_diff = curr_grade - prev_grade

        prev_probs = prev_res.probabilities if prev_res and prev_res.probabilities else {}
        curr_probs = curr_res.probabilities if curr_res and curr_res.probabilities else {}

        prob_shifts = {}
        for grade_idx in range(5):
            key = str(grade_idx)
            p_prev = prev_probs.get(key, 0.0)
            p_curr = curr_probs.get(key, 0.0)
            prob_shifts[key] = round(p_curr - p_prev, 4)

        prev_vtdr = prev_res.vtdr_prob_sum if prev_res else None
        curr_vtdr = curr_res.vtdr_prob_sum if curr_res else None
        vtdr_shift = None
        if prev_vtdr is not None and curr_vtdr is not None:
            vtdr_shift = round(curr_vtdr - prev_vtdr, 4)

        prev_gradable = prev_res.gradable if prev_res else False
        curr_gradable = curr_res.gradable if curr_res else False

        has_prev_expl = prev_expl is not None and prev_expl.status == "completed"
        has_curr_expl = curr_expl is not None and curr_expl.status == "completed"

        review_required = False
        if grade_diff is not None and grade_diff != 0:
            review_required = True
        if vtdr_shift is not None and abs(vtdr_shift) >= 0.10:
            review_required = True

        if not has_prev_img or not has_curr_img:
            summary = f"{eye} scan was not captured in one of the screening sessions. Bilateral longitudinal assessment incomplete."
        elif prev_grade is None or curr_grade is None:
            summary = f"{eye}: Incomplete AI evaluation for one or both visits. Direct grade delta could not be computed."
        elif grade_diff == 0:
            shift_str = f"{vtdr_shift:+.1%}" if vtdr_shift is not None else "0.0%"
            summary = f"{eye}: No recorded grade change ({prev_label} -> {curr_label}, delta 0). AI-estimated VTDR risk change: {shift_str}."
        elif grade_diff > 0:
            shift_str = f"{vtdr_shift:+.1%}" if vtdr_shift is not None else "0.0%"
            summary = f"{eye}: AI-estimated grade increased (+{grade_diff}; {prev_label} -> {curr_label}; requires clinical review). VTDR risk change: {shift_str}."
        else:
            shift_str = f"{vtdr_shift:+.1%}" if vtdr_shift is not None else "0.0%"
            summary = f"{eye}: AI-estimated grade decreased ({grade_diff}; {prev_label} -> {curr_label}; requires clinical review). VTDR risk change: {shift_str}."

        return EyeComparisonResult(
            eye=eye,
            has_previous_image=has_prev_img,
            has_current_image=has_curr_img,
            previous_grade=prev_grade,
            current_grade=curr_grade,
            previous_label=prev_label,
            current_label=curr_label,
            grade_difference=grade_diff,
            previous_probabilities=prev_probs,
            current_probabilities=curr_probs,
            probability_shifts=prob_shifts,
            previous_vtdr_prob=prev_vtdr,
            current_vtdr_prob=curr_vtdr,
            vtdr_risk_shift=vtdr_shift,
            previous_gradable=prev_gradable,
            current_gradable=curr_gradable,
            has_previous_explanation=has_prev_expl,
            has_current_explanation=has_curr_expl,
            neutral_summary=summary,
            review_required_shift=review_required,
        )

    @classmethod
    async def get_screening_comparison(
        cls,
        db: AsyncSession,
        current_screening_id: str,
        current_user: User,
        previous_screening_id: Optional[str] = None,
    ) -> ScreeningComparisonResponse:
        current_screening = await ScreeningRepository.get_by_id_and_owner(db, current_screening_id, current_user.id)
        if not current_screening:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening record not found.")

        patient = await PatientRepository.get_by_id_and_owner(db, current_screening.patient_id, current_user.id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient record not found.")

        if previous_screening_id:
            if previous_screening_id == current_screening_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot compare a screening with itself. Please select an earlier screening.",
                )
            previous_screening = await ScreeningRepository.get_by_id_and_owner(db, previous_screening_id, current_user.id)
            if not previous_screening:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Previous screening record not found.",
                )
            if previous_screening.patient_id != current_screening.patient_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cross-patient comparison forbidden: both screenings must belong to the same patient.",
                )
        else:
            stmt = (
                select(Screening)
                .options(
                    selectinload(Screening.patient).selectinload(Patient.consents),
                    selectinload(Screening.images),
                )
                .where(
                    Screening.patient_id == current_screening.patient_id,
                    Screening.owner_user_id == current_user.id,
                    Screening.id != current_screening.id,
                    Screening.created_at < current_screening.created_at,
                    Screening.status != "cancelled",
                )
                .order_by(desc(Screening.created_at))
                .limit(1)
            )
            res = await db.execute(stmt)
            previous_screening = res.scalars().first()
            if not previous_screening:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No prior screening available for this patient to compare against.",
                )

        days_interval = abs((current_screening.created_at - previous_screening.created_at).days)

        curr_ai_run = await cls.get_latest_ai_run(db, current_screening.id, current_user.id)
        prev_ai_run = await cls.get_latest_ai_run(db, previous_screening.id, current_user.id)

        curr_od_expl = await ClinicalWorkflowRepository.get_explanation_by_eye(db, current_screening.id, current_user.id, "OD")
        curr_os_expl = await ClinicalWorkflowRepository.get_explanation_by_eye(db, current_screening.id, current_user.id, "OS")
        prev_od_expl = await ClinicalWorkflowRepository.get_explanation_by_eye(db, previous_screening.id, current_user.id, "OD")
        prev_os_expl = await ClinicalWorkflowRepository.get_explanation_by_eye(db, previous_screening.id, current_user.id, "OS")

        curr_od_img = next((img for img in current_screening.images if img.eye == "OD" and img.is_current), None)
        curr_os_img = next((img for img in current_screening.images if img.eye == "OS" and img.is_current), None)
        prev_od_img = next((img for img in previous_screening.images if img.eye == "OD" and img.is_current), None)
        prev_os_img = next((img for img in previous_screening.images if img.eye == "OS" and img.is_current), None)

        curr_od_res = next((r for r in curr_ai_run.eye_results if r.eye == "OD"), None) if curr_ai_run else None
        curr_os_res = next((r for r in curr_ai_run.eye_results if r.eye == "OS"), None) if curr_ai_run else None
        prev_od_res = next((r for r in prev_ai_run.eye_results if r.eye == "OD"), None) if prev_ai_run else None
        prev_os_res = next((r for r in prev_ai_run.eye_results if r.eye == "OS"), None) if prev_ai_run else None

        od_comparison = cls._build_eye_comparison("OD", curr_od_img, prev_od_img, curr_od_res, prev_od_res, curr_od_expl, prev_od_expl)
        os_comparison = cls._build_eye_comparison("OS", curr_os_img, prev_os_img, curr_os_res, prev_os_res, curr_os_expl, prev_os_expl)

        is_directly_comparable = True
        comparability_notes = []
        if curr_ai_run and prev_ai_run:
            if curr_ai_run.model_key != prev_ai_run.model_key or curr_ai_run.checkpoint_sha256 != prev_ai_run.checkpoint_sha256:
                is_directly_comparable = False
                comparability_notes.append("Screenings evaluated with differing AI model checkpoints. Probability distributions reflect differing calibration baselines.")
        else:
            is_directly_comparable = False
            comparability_notes.append("One or both screenings lack completed research AI analysis.")

        overall_summary = (
            f"Screening interval: {days_interval} days between encounters. "
            f"{od_comparison.neutral_summary} {os_comparison.neutral_summary} "
            f"Requires clinical correlation by credentialed practitioner."
        )

        await ClinicalWorkflowRepository.append_audit_log(
            db=db,
            owner_user_id=current_user.id,
            actor_user_id=current_user.id,
            screening_id=current_screening.id,
            patient_id=patient.id,
            event_type="SCREENING_COMPARISON_VIEWED",
            summary=f"Compared screening SCR-{current_screening.id[:8].upper()} with prior encounter SCR-{previous_screening.id[:8].upper()}.",
            metadata={
                "current_screening_id": current_screening.id,
                "previous_screening_id": previous_screening.id,
                "days_interval": days_interval,
            },
        )
        await db.commit()

        return ScreeningComparisonResponse(
            patient_id=patient.id,
            patient_name=patient.full_name,
            medical_record_number=patient.patient_code or "",
            current_screening_id=current_screening.id,
            current_screening_reference=f"SCR-{current_screening.id[:8].upper()}",
            current_screening_date=current_screening.created_at,
            previous_screening_id=previous_screening.id,
            previous_screening_reference=f"SCR-{previous_screening.id[:8].upper()}",
            previous_screening_date=previous_screening.created_at,
            days_interval=days_interval,
            is_directly_comparable=is_directly_comparable,
            comparability_notes=comparability_notes,
            od_comparison=od_comparison,
            os_comparison=os_comparison,
            overall_comparison_summary=overall_summary,
            clinical_safety_disclaimer=CLINICAL_SAFETY_NOTICE,
        )

    @classmethod
    async def get_patient_timeline(
        cls,
        db: AsyncSession,
        patient_id: str,
        current_user: User,
    ) -> PatientTimelineResponse:
        patient = await PatientRepository.get_by_id_and_owner(db, patient_id, current_user.id)
        if not patient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient record not found.")

        stmt = (
            select(Screening)
            .options(
                selectinload(Screening.images),
            )
            .where(
                Screening.patient_id == patient.id,
                Screening.owner_user_id == current_user.id,
            )
            .order_by(asc(Screening.created_at))
        )
        res = await db.execute(stmt)
        screenings = res.scalars().all()

        events: List[PatientTimelineEvent] = []
        prior_worst_grade: Optional[int] = None

        for sc in screenings:
            ai_run = await cls.get_latest_ai_run(db, sc.id, current_user.id)
            review = await cls.get_clinical_review(db, sc.id, current_user.id)

            od_res = next((r for r in ai_run.eye_results if r.eye == "OD"), None) if ai_run else None
            os_res = next((r for r in ai_run.eye_results if r.eye == "OS"), None) if ai_run else None

            od_grade = od_res.predicted_grade if od_res else None
            os_grade = os_res.predicted_grade if os_res else None

            grades = [g for g in (od_grade, os_grade) if g is not None]
            worst_g = max(grades) if grades else None
            worst_lbl = CLASS_INDEX_TO_LABEL.get(worst_g) if worst_g is not None else None

            vtdr_risks = [r.vtdr_prob_sum for r in (od_res, os_res) if r and r.vtdr_prob_sum is not None]
            worst_vtdr = max(vtdr_risks) if vtdr_risks else None

            has_od = any(img.eye == "OD" and img.is_current for img in sc.images)
            has_os = any(img.eye == "OS" and img.is_current for img in sc.images)
            is_bilateral = has_od and has_os

            quality_status = "gradable"
            if ai_run:
                if ai_run.overall_status == "quality_failed":
                    quality_status = "quality_failed"
                elif any(not r.gradable for r in (od_res, os_res) if r):
                    quality_status = "partial_ungradable"
            elif not is_bilateral:
                quality_status = "incomplete_capture"
            else:
                quality_status = "pending_assessment"

            trend_cat = "baseline"
            trend_desc = "Initial baseline screening encounter."

            if prior_worst_grade is not None and worst_g is not None:
                delta = worst_g - prior_worst_grade
                if delta == 0:
                    trend_cat = "stable"
                    trend_desc = f"Stable estimated grade ({worst_lbl}, delta 0)."
                elif delta > 0:
                    trend_cat = "higher_grade"
                    trend_desc = f"AI estimated grade higher by {delta} (+{delta}; requires review)."
                else:
                    trend_cat = "lower_grade"
                    trend_desc = f"AI estimated grade lower by {abs(delta)} ({delta}; requires review)."
            elif len(events) > 0 and worst_g is None:
                trend_cat = "unassessed"
                trend_desc = "AI assessment incomplete or missing for this visit."

            if worst_g is not None:
                prior_worst_grade = worst_g

            event = PatientTimelineEvent(
                screening_id=sc.id,
                screening_reference=f"SCR-{sc.id[:8].upper()}",
                screening_date=sc.created_at,
                status=sc.status,
                od_grade=od_grade,
                os_grade=os_grade,
                worst_grade=worst_g,
                worst_label=worst_lbl,
                referable_dr_risk=worst_vtdr,
                is_bilateral_complete=is_bilateral,
                quality_status=quality_status,
                review_status=sc.status,
                reviewer_name=review.reviewer_name if review else None,
                has_ai_run=ai_run is not None,
                report_id=f"RPT-{sc.id[:8].upper()}",
                trend_category=trend_cat,
                trend_description=trend_desc,
            )
            events.append(event)

        summary = f"Longitudinal history for {patient.full_name}: {len(events)} recorded screening encounter(s)."

        return PatientTimelineResponse(
            patient_id=patient.id,
            patient_name=patient.full_name,
            medical_record_number=patient.patient_code or "",
            total_screenings=len(events),
            events=events,
            summary=summary,
            clinical_safety_notice=CLINICAL_SAFETY_NOTICE,
        )

    @classmethod
    async def generate_screening_pdf_report(
        cls,
        db: AsyncSession,
        storage: ImageStorageBackend,
        screening_id: str,
        current_user: User,
    ) -> bytes:
        report_resp = await cls.get_screening_report(db, screening_id, current_user)
        report_dict = report_resp.model_dump()

        screening = await ScreeningRepository.get_by_id_and_owner(db, screening_id, current_user.id)
        if not screening:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Screening record not found.")

        comparison_dict = None
        try:
            comp_resp = await cls.get_screening_comparison(db, screening_id, current_user)
            comparison_dict = comp_resp.model_dump()
        except HTTPException:
            comparison_dict = None

        image_bytes_map: Dict[str, bytes] = {}
        for img in screening.images:
            if img.is_current and img.storage_key:
                try:
                    raw_b = await storage.read_bytes(img.storage_key)
                    image_bytes_map[f"{img.eye}_original"] = raw_b
                except Exception as exc:
                    logger.warning(f"Could not read {img.eye} original scan for PDF: {exc}")

        od_exp = await ClinicalWorkflowRepository.get_explanation_by_eye(db, screening.id, current_user.id, "OD")
        if od_exp and od_exp.overlay_storage_key:
            try:
                ov_b = await storage.read_bytes(od_exp.overlay_storage_key)
                image_bytes_map["OD_overlay"] = ov_b
            except Exception as exc:
                logger.warning(f"Could not read OD overlay for PDF: {exc}")

        os_exp = await ClinicalWorkflowRepository.get_explanation_by_eye(db, screening.id, current_user.id, "OS")
        if os_exp and os_exp.overlay_storage_key:
            try:
                ov_b = await storage.read_bytes(os_exp.overlay_storage_key)
                image_bytes_map["OS_overlay"] = ov_b
            except Exception as exc:
                logger.warning(f"Could not read OS overlay for PDF: {exc}")

        await ClinicalWorkflowRepository.append_audit_log(
            db=db,
            owner_user_id=current_user.id,
            actor_user_id=current_user.id,
            screening_id=screening.id,
            patient_id=screening.patient_id,
            event_type="SCREENING_PDF_EXPORTED",
            summary=f"Official clinical PDF report generated and exported by {current_user.full_name}.",
            metadata={"screening_id": screening.id, "report_id": report_dict.get("report_id")},
        )
        await db.commit()

        pdf_bytes = PdfReportService.generate_pdf(
            report_data=report_dict,
            comparison_data=comparison_dict,
            image_bytes_map=image_bytes_map,
        )
        return pdf_bytes
