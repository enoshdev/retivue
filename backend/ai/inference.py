"""Isolated quality-gated 5-class DR inference interface (never auto-diagnoses or alters raw images)."""

import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import torch
from PIL import Image, ImageOps

from ai.checkpoint import verify_and_load_checkpoint
from ai.config import CLASS_INDEX_TO_LABEL, IMAGENET_MEAN, IMAGENET_STD, resolve_torch_device
from ai.models import build_classifier_model
from ai.transforms import build_retinal_transforms
from data_pipeline.preprocessor import (
    PreprocessingConfig,
    _convert_image_to_rgb_safely,
    _resize_preserving_aspect_ratio_letterbox_cv,
    detect_retinal_fov_bbox,
)


@dataclass(frozen=True)
class InferenceAdvisoryResult:
    gradable: bool
    quality_status: str  # 'gradable', 'ungradable_image_quality', 'decode_error'
    quality_reason: Optional[str]
    predicted_grade: Optional[int]
    predicted_label: Optional[str]
    probabilities_by_class: Dict[str, float]
    confidence_max_prob: Optional[float]
    uncertainty_review_required: bool
    uncertainty_reason: Optional[str]
    checkpoint_sha256: str
    advisory_disclaimer: str


class DRBaselinePredictor:
    """
    Standalone inference wrapper that enforces retinal FOV & image usability checks BEFORE neural
    network scoring and marks low-confidence / narrow-margin predictions for mandatory human review.
    """

    ADVISORY_DISCLAIMER = (
        "AI-assisted screening research output only — NOT a clinical diagnosis. "
        "Requires independent review and sign-off by a qualified eye-care professional."
    )

    def __init__(
        self,
        checkpoint_path: Path,
        expected_sha256: Optional[str] = None,
        device_preference: str = "auto",
        min_confidence_for_auto_tier: float = 0.60,
        min_top2_margin: float = 0.15,
        enable_hardened_quality_gate: bool = True,
    ) -> None:
        self.checkpoint_path = Path(checkpoint_path)
        self.min_confidence = min_confidence_for_auto_tier
        self.min_top2_margin = min_top2_margin

        dev_info = resolve_torch_device(device_preference)
        self.device = torch.device(dev_info["device"])

        ckpt = verify_and_load_checkpoint(
            self.checkpoint_path,
            expected_sha256=expected_sha256,
            map_location="cpu",
        )
        self.checkpoint_sha256 = str(ckpt["_verified_sha256"])
        self.architecture = str(ckpt.get("architecture", "efficientnet_b0"))
        self.num_classes = int(ckpt.get("num_classes", 5))
        self.input_size = int(ckpt.get("input_size", 512))
        self.dropout_p = float(ckpt.get("dropout_p", 0.3))
        self.norm_mean = tuple(float(x) for x in ckpt.get("norm_mean", IMAGENET_MEAN))
        self.norm_std = tuple(float(x) for x in ckpt.get("norm_std", IMAGENET_STD))
        raw_cmap = ckpt.get("class_mapping", CLASS_INDEX_TO_LABEL)
        self.class_mapping: Dict[int, str] = {int(k): str(v) for k, v in raw_cmap.items()}

        self.model = build_classifier_model(
            architecture=self.architecture,
            num_classes=self.num_classes,
            pretrained=False,
            dropout_p=self.dropout_p,
        )
        self.model.load_state_dict(ckpt["model_state_dict"])
        self.model.to(self.device)
        self.model.eval()

        self.prep_config = (
            PreprocessingConfig.phase11_hardened_preset(
                target_size=(self.input_size, self.input_size),
                clahe_applied=False,
            )
            if enable_hardened_quality_gate
            else PreprocessingConfig.phase8_aptos_preset(
                target_size=(self.input_size, self.input_size),
                clahe_applied=False,
            )
        )
        self.eval_transform = build_retinal_transforms(
            input_size=self.input_size,
            mean=self.norm_mean,  # type: ignore[arg-type]
            std=self.norm_std,  # type: ignore[arg-type]
            is_train=False,
            augmentation_enabled=False,
        )

    def predict_from_bytes(self, raw_image_bytes: bytes) -> InferenceAdvisoryResult:
        """
        Inspect raw image bytes in-memory -> enforce FOV & quality gate -> return advisory probabilities
        without mutating original bytes or forcing a DR grade on ungradable uploads.
        """
        try:
            with Image.open(io.BytesIO(raw_image_bytes)) as img:
                img.load()
                transposed = ImageOps.exif_transpose(img)
                rgb = _convert_image_to_rgb_safely(transposed)
                rgb_arr = np.asarray(rgb, dtype=np.uint8)
        except Exception as exc:
            return InferenceAdvisoryResult(
                gradable=False,
                quality_status="decode_error",
                quality_reason=f"Failed to decode image payload: {exc.__class__.__name__}",
                predicted_grade=None,
                predicted_label=None,
                probabilities_by_class={},
                confidence_max_prob=None,
                uncertainty_review_required=True,
                uncertainty_reason="Image failed integrity decoding; clinical review / recapture required.",
                checkpoint_sha256=self.checkpoint_sha256,
                advisory_disclaimer=self.ADVISORY_DISCLAIMER,
            )

        bbox, _metrics, err_reason = detect_retinal_fov_bbox(rgb_arr, self.prep_config)
        if err_reason is not None or bbox is None:
            return InferenceAdvisoryResult(
                gradable=False,
                quality_status="ungradable_image_quality",
                quality_reason=err_reason or "Image failed retinal FOV / illumination usability gate.",
                predicted_grade=None,
                predicted_label=None,
                probabilities_by_class={},
                confidence_max_prob=None,
                uncertainty_review_required=True,
                uncertainty_reason="Ungradable image; model refuses to force a DR severity grade.",
                checkpoint_sha256=self.checkpoint_sha256,
                advisory_disclaimer=self.ADVISORY_DISCLAIMER,
            )

        x1, y1, x2, y2 = bbox
        cropped = rgb_arr[y1:y2, x1:x2]
        padded_rgb, _, _, _ = _resize_preserving_aspect_ratio_letterbox_cv(
            cropped,
            self.input_size,
            self.input_size,
            down_interp=self.prep_config.downscale_interpolation,
            up_interp=self.prep_config.upscale_interpolation,
        )
        tensor = self.eval_transform(Image.fromarray(padded_rgb, mode="RGB")).unsqueeze(0).to(self.device)

        with torch.inference_mode():
            logits = self.model(tensor)
            probs_t = torch.softmax(logits, dim=1).squeeze(0).detach().cpu().numpy()

        probs_map = {
            self.class_mapping[i]: round(float(probs_t[i]), 6)
            for i in sorted(self.class_mapping.keys())
        }
        top_idx = int(np.argmax(probs_t))
        sorted_probs = np.sort(probs_t)[::-1]
        max_prob = float(sorted_probs[0])
        margin = float(sorted_probs[0] - sorted_probs[1]) if len(sorted_probs) > 1 else max_prob

        uncertain_reasons = []
        if max_prob < self.min_confidence:
            uncertain_reasons.append(f"max_probability={max_prob:.3f} < {self.min_confidence:.2f}")
        if margin < self.min_top2_margin:
            uncertain_reasons.append(f"top2_margin={margin:.3f} < {self.min_top2_margin:.2f}")

        return InferenceAdvisoryResult(
            gradable=True,
            quality_status="gradable",
            quality_reason=None,
            predicted_grade=top_idx,
            predicted_label=self.class_mapping[top_idx],
            probabilities_by_class=probs_map,
            confidence_max_prob=round(max_prob, 6),
            uncertainty_review_required=bool(uncertain_reasons),
            uncertainty_reason="; ".join(uncertain_reasons) if uncertain_reasons else None,
            checkpoint_sha256=self.checkpoint_sha256,
            advisory_disclaimer=self.ADVISORY_DISCLAIMER,
        )
