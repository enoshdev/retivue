import io
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import anyio
import numpy as np
from PIL import Image, ImageOps

from app.core.config import settings
from app.core.logging import logger
from app.schemas.clinical_workflow import (
    AiModelRegistryItem,
    AiEyeResultResponse,
    AiRunResponse,
)
from app.models.screening_ai import ScreeningAiRun, ScreeningAiEyeResult, ScreeningAiExplanation

from ai.checkpoint import compute_checkpoint_sha256
from ai.config import CLASS_INDEX_TO_LABEL
from ai.inference import DRBaselinePredictor
from ai.reliability import compute_retinal_quality_diagnostics
from ai.gradcam import GradCAMGenerator, generate_explanation_text
from data_pipeline.preprocessor import (
    PreprocessingConfig,
    _convert_image_to_rgb_safely,
)


RESEARCH_DISCLAIMER = (
    "AI-assisted screening research decision-support only — NOT a clinical diagnosis. "
    "Requires independent review and sign-off by a qualified eye-care professional."
)

CALIBRATION_WARNING = (
    "Softmax output values represent model classification confidence on training distributions "
    "and must NOT be interpreted as calibrated clinical probabilities."
)

# Registry of preserved frozen research checkpoints from Phase 9/10/11
MODEL_REGISTRY_CONFIG: Dict[str, Dict[str, Any]] = {
    "aptos_e0_unweighted": {
        "model_version": "phase9_e0_unweighted_v1",
        "architecture": "efficientnet_b0",
        "training_strategy": "Baseline Cross-Entropy (unweighted)",
        "relative_checkpoint_path": "experiments/aptos_e0_unweighted/best_checkpoint.pt",
        "expected_sha256": "e5bee28ee33950314963010bff68b6ec4340421aba2c65ef6df97a8e9a702610",
        "checkpoint_epoch": 6,
        "is_default": False,
        "status_note": "Baseline unweighted model preserved from Phase 9.",
    },
    "aptos_e1_weighted_effective": {
        "model_version": "phase9_e1_weighted_v1",
        "architecture": "efficientnet_b0",
        "training_strategy": "Class-Weighted Cross-Entropy (effective samples)",
        "relative_checkpoint_path": "experiments/aptos_e1_weighted_effective/best_checkpoint.pt",
        "expected_sha256": "0d797123d9ff7ee3577ba93a79d1169753f3984b5dcf75889949a7c656423518",
        "checkpoint_epoch": 4,
        "is_default": False,
        "status_note": "Cost-sensitive weighted loss model preserved from Phase 9.",
    },
    "aptos_e2_weighted_sampler": {
        "model_version": "phase9_e2_sampler_v1",
        "architecture": "efficientnet_b0",
        "training_strategy": "Weighted Random Sampler (balanced batching)",
        "relative_checkpoint_path": "experiments/aptos_e2_weighted_sampler/best_checkpoint.pt",
        "expected_sha256": "a94c4d0e2ac2e5200dabe6da122337f7a4191557dba5c02c85e52014b168686b",
        "checkpoint_epoch": 4,
        "is_default": True,
        "status_note": "Default evaluation checkpoint with highest VTDR sensitivity and entropy coverage.",
    },
}

_PREDICTOR_CACHE: Dict[str, DRBaselinePredictor] = {}


class AiScreeningService:
    """
    Modular backend service for quality-gated research AI screening.
    Ensures strict model provenance, refusal to force grades on ungradable eyes,
    and automatic escalation for uncertainty and high-risk findings.
    """

    @classmethod
    def get_registered_models(cls) -> List[AiModelRegistryItem]:
        items: List[AiModelRegistryItem] = []
        model_root = Path(settings.MODEL_ROOT)

        for key, meta in MODEL_REGISTRY_CONFIG.items():
            ckpt_path = model_root / meta["relative_checkpoint_path"]
            exists = ckpt_path.is_file()
            items.append(
                AiModelRegistryItem(
                    model_key=key,
                    model_version=meta["model_version"],
                    architecture=meta["architecture"],
                    training_strategy=meta["training_strategy"],
                    checkpoint_sha256=meta["expected_sha256"],
                    checkpoint_epoch=meta["checkpoint_epoch"],
                    is_default=(key == settings.DEFAULT_AI_MODEL_KEY),
                    checkpoint_present=exists,
                    status_note=meta["status_note"],
                )
            )
        return items

    @classmethod
    def get_or_load_predictor(cls, model_key: Optional[str] = None) -> Tuple[DRBaselinePredictor, Dict[str, Any]]:
        target_key = model_key or settings.DEFAULT_AI_MODEL_KEY
        if target_key not in MODEL_REGISTRY_CONFIG:
            raise ValueError(f"Unknown AI model key '{target_key}'. Available: {list(MODEL_REGISTRY_CONFIG.keys())}")

        meta = MODEL_REGISTRY_CONFIG[target_key]
        if target_key in _PREDICTOR_CACHE:
            return _PREDICTOR_CACHE[target_key], meta

        model_root = Path(settings.MODEL_ROOT)
        ckpt_path = model_root / meta["relative_checkpoint_path"]
        if not ckpt_path.is_file():
            raise FileNotFoundError(f"Model checkpoint not found at {ckpt_path}")

        # Compute SHA-256 before loading
        actual_sha = compute_checkpoint_sha256(ckpt_path)
        if actual_sha.lower() != meta["expected_sha256"].lower():
            raise ValueError(
                f"Checkpoint SHA-256 integrity check failed for '{target_key}': "
                f"expected {meta['expected_sha256']}, got {actual_sha}."
            )

        logger.info(f"Verified checkpoint integrity for '{target_key}' ({actual_sha[:16]}...). Loading weights.")
        predictor = DRBaselinePredictor(
            checkpoint_path=ckpt_path,
            expected_sha256=meta["expected_sha256"],
            device_preference="cpu",
            min_confidence_for_auto_tier=0.60,
            min_top2_margin=0.15,
            enable_hardened_quality_gate=True,
        )
        _PREDICTOR_CACHE[target_key] = predictor
        return predictor, meta

    @classmethod
    def _evaluate_eye_sync(
        cls,
        predictor: DRBaselinePredictor,
        raw_bytes: bytes,
    ) -> Dict[str, Any]:
        """
        Synchronous execution of hardened quality diagnostics and (if gradable) DR inference.
        Must be invoked in an off-thread worker to prevent event loop blocking.
        """
        # 1. Quality diagnostics via Phase 11 hardened preset
        prep_cfg = PreprocessingConfig.phase11_hardened_preset(
            target_size=(predictor.input_size, predictor.input_size),
            clahe_applied=False,
        )

        try:
            with Image.open(io.BytesIO(raw_bytes)) as pil_img:
                pil_img.load()
                transposed = ImageOps.exif_transpose(pil_img)
                rgb_pil = _convert_image_to_rgb_safely(transposed)
                rgb_arr = np.asarray(rgb_pil, dtype=np.uint8)
        except Exception as exc:
            return {
                "gradable": False,
                "quality_status": "decode_error",
                "quality_reason": f"Failed to decode image bytes: {exc.__class__.__name__}",
                "quality_metrics": {},
                "predicted_grade": None,
                "predicted_label": None,
                "probabilities": {},
                "confidence_max_prob": None,
                "top2_margin": None,
                "normalized_entropy": None,
                "vtdr_prob_sum": None,
                "uncertainty_review_required": True,
                "uncertainty_reasons": ["Image decoding failure; recapture required."],
                "high_risk_flagged": False,
                "cam_data": {
                    "status": "unavailable_ungradable",
                    "target_class": 0,
                    "target_class_label": "No_DR",
                    "explanation_text": generate_explanation_text(None, 0, {}, "image decoding failure"),
                    "model_layer": "features.8",
                    "heatmap_bytes": None,
                    "overlay_bytes": None,
                },
            }

        diag = compute_retinal_quality_diagnostics(rgb_arr, config=prep_cfg)

        # 2. Run inference predictor
        pred_result = predictor.predict_from_bytes(raw_bytes)

        if not pred_result.gradable:
            # Ungradable eye: NEVER force grade or label
            quality_reason = pred_result.quality_reason or (
                "; ".join(diag.get("phase10_extended_reasons", [])) or "Retinal quality gate failed"
            )
            return {
                "gradable": False,
                "quality_status": pred_result.quality_status,
                "quality_reason": quality_reason,
                "quality_metrics": diag,
                "predicted_grade": None,
                "predicted_label": None,
                "probabilities": {},
                "confidence_max_prob": None,
                "top2_margin": None,
                "normalized_entropy": None,
                "vtdr_prob_sum": None,
                "uncertainty_review_required": True,
                "uncertainty_reasons": ["Ungradable image quality: grade withheld, recapture required."],
                "high_risk_flagged": False,
                "cam_data": {
                    "status": "unavailable_ungradable",
                    "target_class": 0,
                    "target_class_label": "No_DR",
                    "explanation_text": generate_explanation_text(None, 0, {}, quality_reason),
                    "model_layer": "features.8",
                    "heatmap_bytes": None,
                    "overlay_bytes": None,
                },
            }

        # 3. Gradable eye: parse probabilities, calculate normalized entropy and VTDR risk
        probs = pred_result.probabilities_by_class
        prob_arr = np.array([probs.get(CLASS_INDEX_TO_LABEL[i], 0.0) for i in range(5)], dtype=float)
        prob_sum = float(np.sum(prob_arr))
        if prob_sum > 0:
            prob_arr = prob_arr / prob_sum

        clipped_p = np.clip(prob_arr, 1e-12, 1.0)
        entropy = -float(np.sum(clipped_p * np.log(clipped_p)))
        norm_entropy = round(entropy / math.log(5), 4)

        vtdr_prob = round(float(prob_arr[2] + prob_arr[3] + prob_arr[4]), 4)
        top_grade = pred_result.predicted_grade
        top_label = pred_result.predicted_label

        uncertainty_reasons: List[str] = []
        if pred_result.confidence_max_prob is not None and pred_result.confidence_max_prob < 0.60:
            uncertainty_reasons.append(f"Low confidence ({pred_result.confidence_max_prob:.3f} < 0.60)")
        top2_margin = (
            round(float(np.sort(prob_arr)[-1] - np.sort(prob_arr)[-2]), 4)
            if len(prob_arr) > 1
            else 1.0
        )
        if top2_margin < 0.15:
            uncertainty_reasons.append(f"Narrow top-2 margin ({top2_margin:.3f} < 0.15)")
        if norm_entropy > 0.55:
            uncertainty_reasons.append(f"High prediction entropy ({norm_entropy:.3f} > 0.55)")

        high_risk = bool(top_grade is not None and top_grade >= 2) or (vtdr_prob >= 0.40)
        if high_risk:
            uncertainty_reasons.append(f"Elevated VTDR risk (Grade {top_grade}, VTDR prob={vtdr_prob:.3f})")

        # 4. Generate genuine Grad-CAM explainability for predicted grade
        cam_data: Dict[str, Any]
        if top_grade is not None:
            try:
                gradcam_gen = GradCAMGenerator(predictor.model)
                cam_res = gradcam_gen.generate_aligned_cam(
                    raw_image_bytes=raw_bytes,
                    eval_transform=predictor.eval_transform,
                    prep_config=prep_cfg,
                    device=predictor.device,
                    target_class=top_grade,
                )
                exp_text = generate_explanation_text(top_grade, top_grade, probs, None)
                cam_data = {
                    "status": "completed",
                    "target_class": top_grade,
                    "target_class_label": top_label,
                    "explanation_text": exp_text,
                    "model_layer": gradcam_gen.layer_name,
                    "heatmap_bytes": cam_res["heatmap_png_bytes"],
                    "overlay_bytes": cam_res["overlay_png_bytes"],
                }
            except Exception as cam_exc:
                logger.warning(f"Grad-CAM generation failed: {cam_exc}")
                cam_data = {
                    "status": "failed",
                    "target_class": top_grade,
                    "target_class_label": top_label,
                    "explanation_text": f"Grad-CAM generation encountered an unexpected error: {cam_exc}",
                    "model_layer": "features.8",
                    "heatmap_bytes": None,
                    "overlay_bytes": None,
                }
        else:
            cam_data = {
                "status": "unavailable_ungradable",
                "target_class": 0,
                "target_class_label": "No_DR",
                "explanation_text": generate_explanation_text(None, 0, {}, None),
                "model_layer": "features.8",
                "heatmap_bytes": None,
                "overlay_bytes": None,
            }

        return {
            "gradable": True,
            "quality_status": "gradable",
            "quality_reason": None,
            "quality_metrics": diag,
            "predicted_grade": top_grade,
            "predicted_label": top_label,
            "probabilities": probs,
            "confidence_max_prob": pred_result.confidence_max_prob,
            "top2_margin": top2_margin,
            "normalized_entropy": norm_entropy,
            "vtdr_prob_sum": vtdr_prob,
            "uncertainty_review_required": bool(uncertainty_reasons),
            "uncertainty_reasons": uncertainty_reasons,
            "high_risk_flagged": high_risk,
            "cam_data": cam_data,
        }

    @classmethod
    async def run_ai_screening(
        cls,
        screening_id: str,
        owner_user_id: str,
        triggered_by_user_id: str,
        od_image_id: str,
        od_bytes: bytes,
        os_image_id: str,
        os_bytes: bytes,
        model_key: Optional[str] = None,
    ) -> Tuple[ScreeningAiRun, List[ScreeningAiEyeResult], Dict[str, Dict[str, Any]]]:
        """
        Executes bilateral AI screening on OD and OS images in parallel background threads.
        Constructs immutable ORM models ready for database persistence.
        """
        predictor, meta = cls.get_or_load_predictor(model_key)
        start_t = time.perf_counter()

        # Run OD and OS analysis concurrently on thread pool
        async with anyio.create_task_group() as tg:
            od_eval_box: List[Dict[str, Any]] = []
            os_eval_box: List[Dict[str, Any]] = []

            async def _run_od():
                res = await anyio.to_thread.run_sync(cls._evaluate_eye_sync, predictor, od_bytes)
                od_eval_box.append(res)

            async def _run_os():
                res = await anyio.to_thread.run_sync(cls._evaluate_eye_sync, predictor, os_bytes)
                os_eval_box.append(res)

            tg.start_soon(_run_od)
            tg.start_soon(_run_os)

        exec_ms = int((time.perf_counter() - start_t) * 1000)
        od_res = od_eval_box[0]
        os_res = os_eval_box[0]

        # Determine overall encounter findings
        all_gradable = od_res["gradable"] and os_res["gradable"]
        any_ungradable = (not od_res["gradable"]) or (not os_res["gradable"])

        overall_escalation: List[str] = []
        if any_ungradable:
            if not od_res["gradable"]:
                overall_escalation.append(f"OD (Right eye) ungradable: {od_res['quality_reason']}")
            if not os_res["gradable"]:
                overall_escalation.append(f"OS (Left eye) ungradable: {os_res['quality_reason']}")

        for eye_label, res in [("OD", od_res), ("OS", os_res)]:
            for r in res["uncertainty_reasons"]:
                overall_escalation.append(f"{eye_label}: {r}")

        overall_review_req = bool(overall_escalation) or any_ungradable
        overall_status = "quality_failed" if any_ungradable else "completed"

        # Higher risk eye determination
        higher_risk_eye: Optional[str] = None
        highest_grade: Optional[int] = None
        highest_label: Optional[str] = None

        od_grade = od_res["predicted_grade"]
        os_grade = os_res["predicted_grade"]

        if od_grade is not None and os_grade is not None:
            if od_grade > os_grade:
                higher_risk_eye = "OD"
                highest_grade = od_grade
                highest_label = od_res["predicted_label"]
            elif os_grade > od_grade:
                higher_risk_eye = "OS"
                highest_grade = os_grade
                highest_label = os_res["predicted_label"]
            else:
                highest_grade = od_grade
                highest_label = od_res["predicted_label"]
                # tie-breaker by VTDR prob or top confidence
                od_vtdr = od_res["vtdr_prob_sum"] or 0.0
                os_vtdr = os_res["vtdr_prob_sum"] or 0.0
                higher_risk_eye = "OD" if od_vtdr >= os_vtdr else "OS"
        elif od_grade is not None:
            higher_risk_eye = "OD"
            highest_grade = od_grade
            highest_label = od_res["predicted_label"]
        elif os_grade is not None:
            higher_risk_eye = "OS"
            highest_grade = os_grade
            highest_label = os_res["predicted_label"]

        prep_dict = {
            "name": "phase11_hardened_preset",
            "input_size": predictor.input_size,
            "clahe_applied": False,
            "min_laplacian_variance": 15.0,
            "min_local_rms_contrast": 1.0,
            "max_fov_aspect_ratio": 1.65,
        }

        ai_run = ScreeningAiRun(
            screening_id=screening_id,
            owner_user_id=owner_user_id,
            triggered_by_user_id=triggered_by_user_id,
            model_key=model_key or settings.DEFAULT_AI_MODEL_KEY,
            model_version=meta["model_version"],
            architecture=meta["architecture"],
            checkpoint_sha256=meta["expected_sha256"],
            checkpoint_epoch=meta["checkpoint_epoch"],
            preprocessing_config_json=json.dumps(prep_dict),
            overall_status=overall_status,
            overall_review_required=overall_review_req,
            overall_escalation_reasons_json=json.dumps(overall_escalation),
            higher_risk_eye=higher_risk_eye,
            highest_predicted_grade=highest_grade,
            highest_predicted_label=highest_label,
            research_disclaimer=RESEARCH_DISCLAIMER,
            calibration_warning=CALIBRATION_WARNING,
            execution_ms=exec_ms,
            inference_timestamp=datetime.now(timezone.utc),
        )

        eye_results: List[ScreeningAiEyeResult] = []
        for eye_str, img_id, eval_dict in [("OD", od_image_id, od_res), ("OS", os_image_id, os_res)]:
            eye_model = ScreeningAiEyeResult(
                screening_id=screening_id,
                screening_image_id=img_id,
                eye=eye_str,
                gradable=eval_dict["gradable"],
                quality_status=eval_dict["quality_status"],
                quality_reason=eval_dict["quality_reason"],
                quality_metrics_json=json.dumps(eval_dict["quality_metrics"]),
                predicted_grade=eval_dict["predicted_grade"],
                predicted_label=eval_dict["predicted_label"],
                probabilities_json=json.dumps(eval_dict["probabilities"]),
                confidence_max_prob=eval_dict["confidence_max_prob"],
                top2_margin=eval_dict["top2_margin"],
                normalized_entropy=eval_dict["normalized_entropy"],
                vtdr_prob_sum=eval_dict["vtdr_prob_sum"],
                uncertainty_review_required=eval_dict["uncertainty_review_required"],
                uncertainty_reasons_json=json.dumps(eval_dict["uncertainty_reasons"]),
                high_risk_flagged=eval_dict["high_risk_flagged"],
            )
            eye_results.append(eye_model)

        cam_dict = {"OD": od_res["cam_data"], "OS": os_res["cam_data"]}
        return ai_run, eye_results, cam_dict

    @classmethod
    def generate_gradcam_on_demand_sync(
        cls,
        predictor: DRBaselinePredictor,
        raw_bytes: bytes,
        target_class: int,
    ) -> Dict[str, Any]:
        prep_cfg = PreprocessingConfig.phase11_hardened_preset(
            target_size=(predictor.input_size, predictor.input_size),
            clahe_applied=False,
        )
        pred_res = predictor.predict_from_bytes(raw_bytes)
        if not pred_res.gradable:
            return {
                "status": "unavailable_ungradable",
                "target_class": target_class,
                "target_class_label": CLASS_INDEX_TO_LABEL.get(target_class, f"Grade_{target_class}"),
                "explanation_text": generate_explanation_text(None, target_class, {}, pred_res.quality_reason),
                "model_layer": "features.8",
                "heatmap_bytes": None,
                "overlay_bytes": None,
            }

        gradcam_gen = GradCAMGenerator(predictor.model)
        cam_res = gradcam_gen.generate_aligned_cam(
            raw_image_bytes=raw_bytes,
            eval_transform=predictor.eval_transform,
            prep_config=prep_cfg,
            device=predictor.device,
            target_class=target_class,
        )
        exp_text = generate_explanation_text(
            pred_res.predicted_grade,
            target_class,
            pred_res.probabilities_by_class,
            None,
        )
        return {
            "status": "completed",
            "target_class": target_class,
            "target_class_label": CLASS_INDEX_TO_LABEL.get(target_class, f"Grade_{target_class}"),
            "explanation_text": exp_text,
            "model_layer": gradcam_gen.layer_name,
            "heatmap_bytes": cam_res["heatmap_png_bytes"],
            "overlay_bytes": cam_res["overlay_png_bytes"],
        }

    @classmethod
    async def generate_explanation_for_image_bytes(
        cls,
        raw_bytes: bytes,
        target_class: int,
        model_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        predictor, _meta = cls.get_or_load_predictor(model_key)
        return await anyio.to_thread.run_sync(
            cls.generate_gradcam_on_demand_sync,
            predictor,
            raw_bytes,
            target_class,
        )
