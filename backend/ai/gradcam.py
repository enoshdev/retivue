"""
RETIVUE Genuine Grad-CAM Explainability Engine.

Computes exact gradient-weighted class activation maps (Grad-CAM) using the
trained EfficientNet-B0 convolutional feature stage (model.features[8]).
Aligns the activation map back to the original uncropped retinal fundus image
coordinates and generates transparent heatmap and blended overlay artifacts.
"""

from __future__ import annotations

import io
from typing import Dict, List, Optional, Tuple, Any

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image, ImageOps

from ai.config import CLASS_INDEX_TO_LABEL
from data_pipeline.preprocessor import (
    PreprocessingConfig,
    _convert_image_to_rgb_safely,
    _resize_preserving_aspect_ratio_letterbox_cv,
    detect_retinal_fov_bbox,
)


# Standard clinical and research explanation templates based strictly on model outputs
EXPLANATION_TEMPLATES = {
    0: (
        "The model assigned the highest probability ({prob:.1f}%) to No Diabetic Retinopathy (Grade 0). "
        "The Grad-CAM attention map indicates broad baseline illumination and background fundus patterns "
        "with no focal regional activations indicating vascular lesions. This screening result does not rule "
        "out disease and requires qualified eye-care professional interpretation."
    ),
    1: (
        "The model assigned the highest probability ({prob:.1f}%) to Mild Non-Proliferative DR (Grade 1). "
        "The Grad-CAM visualization highlights localized image regions that contributed most strongly to this classification. "
        "This attention map reflects neural activation patterns and does not establish the presence of specific microaneurysms."
    ),
    2: (
        "The model assigned the highest probability ({prob:.1f}%) to Moderate Non-Proliferative DR (Grade 2). "
        "The Grad-CAM visualization highlights image regions that contributed most strongly to this classification. "
        "This attention map reflects neural activation patterns across the vascular arcade and does not establish the presence of specific retinal lesions."
    ),
    3: (
        "The model assigned the highest probability ({prob:.1f}%) to Severe Non-Proliferative DR (Grade 3). "
        "The Grad-CAM visualization highlights high-weight regions driving this classification. "
        "Elevated VTDR severity patterns detected; priority specialist ophthalmology evaluation is indicated."
    ),
    4: (
        "The model assigned the highest probability ({prob:.1f}%) to Proliferative Diabetic Retinopathy (Grade 4). "
        "The Grad-CAM visualization highlights prominent retinal zones driving this high-risk classification. "
        "Immediate vitreoretinal clinical consultation and comprehensive slit-lamp/OCT examination are recommended."
    ),
}

UNGRADABLE_EXPLANATION = (
    "Image quality gate failed ({quality_reason}). The AI model refused to produce a disease classification "
    "or Grad-CAM explanation to prevent diagnostic misinformation. Re-capture required."
)


def generate_explanation_text(
    predicted_grade: Optional[int],
    target_class: int,
    probabilities: Dict[str, float],
    quality_reason: Optional[str] = None,
) -> str:
    """
    Generates a concise, responsible clinical explanation based on actual model outputs.
    Never invents microaneurysms, hemorrhages, or exudates from an image-level classifier.
    """
    if predicted_grade is None:
        reason = quality_reason or "retinal usability checks failed"
        return UNGRADABLE_EXPLANATION.format(quality_reason=reason)

    label = CLASS_INDEX_TO_LABEL.get(target_class, f"Grade {target_class}")
    target_prob = probabilities.get(label, 0.0) * 100.0

    if target_class in EXPLANATION_TEMPLATES:
        base_text = EXPLANATION_TEMPLATES[target_class].format(prob=target_prob)
        if target_class != predicted_grade:
            pred_label = CLASS_INDEX_TO_LABEL.get(predicted_grade, f"Grade {predicted_grade}")
            return (
                f"[Alternative Target Analysis: {label}] While the model's top prediction is {pred_label}, "
                f"this Grad-CAM map visualizes the specific features associated with {label} ({target_prob:.1f}% probability). "
                + base_text
            )
        return base_text

    return (
        f"The model evaluated this retinal image with target focus on {label} ({target_prob:.1f}% probability). "
        "Grad-CAM highlights regions influencing this classification score. Requires professional review."
    )


class GradCAMGenerator:
    """
    Genuine Grad-CAM implementation for EfficientNet-B0 classifiers.
    Extracts gradient activations from the final convolutional feature layer (model.features[8]),
    computes GAP channel importance, applies ReLU, and accurately re-aligns to original fundus geometry.
    """

    def __init__(
        self,
        model: nn.Module,
        target_layer: Optional[nn.Module] = None,
        layer_name: str = "features.8",
    ) -> None:
        self.model = model
        self.layer_name = layer_name
        if target_layer is not None:
            self.target_layer = target_layer
        elif hasattr(model, "features") and len(model.features) > 8:
            self.target_layer = model.features[8]
        elif hasattr(model, "features"):
            self.target_layer = model.features[-1]
        else:
            raise ValueError("Could not automatically locate target convolutional stage in model.")

    def compute_cam(
        self,
        input_tensor: torch.Tensor,
        target_class: Optional[int] = None,
    ) -> Tuple[np.ndarray, int, float]:
        """
        Computes the raw normalized Grad-CAM activation map for the given input tensor.
        Returns: (cam_16x16, target_class, score)
        """
        activations: List[torch.Tensor] = []
        gradients: List[torch.Tensor] = []

        def forward_hook(module: nn.Module, inp: Any, out: torch.Tensor) -> None:
            activations.append(out)

        def backward_hook(module: nn.Module, grad_in: Any, grad_out: Tuple[torch.Tensor, ...]) -> None:
            gradients.append(grad_out[0])

        fwd_handle = self.target_layer.register_forward_hook(forward_hook)
        bwd_handle = self.target_layer.register_full_backward_hook(backward_hook)

        was_training = self.model.training
        self.model.eval()

        try:
            with torch.enable_grad():
                tensor_var = input_tensor.clone().detach().requires_grad_(True)
                self.model.zero_grad()
                logits = self.model(tensor_var)

                if target_class is None:
                    target_c = int(torch.argmax(logits, dim=1).item())
                else:
                    target_c = int(target_class)

                score = logits[0, target_c]
                score.backward(retain_graph=False)

            if not activations or not gradients:
                raise RuntimeError("Grad-CAM hooks failed to capture feature activations or gradients.")

            act = activations[0].detach()   # [1, C, H, W]
            grad = gradients[0].detach()    # [1, C, H, W]

            # Global average pooling of gradients over spatial dimensions (H, W)
            weights = torch.mean(grad, dim=(2, 3), keepdim=True)  # [1, C, 1, 1]

            # Weighted combination of feature maps followed by ReLU
            cam_t = torch.relu(torch.sum(weights * act, dim=1, keepdim=True))  # [1, 1, H, W]
            cam_arr = cam_t.squeeze().cpu().numpy()  # [H, W]

            # Min-Max normalization with epsilon guard
            cam_min, cam_max = float(cam_arr.min()), float(cam_arr.max())
            if (cam_max - cam_min) > 1e-8:
                cam_norm = (cam_arr - cam_min) / (cam_max - cam_min)
            else:
                cam_norm = np.zeros_like(cam_arr, dtype=np.float32)

            return cam_norm.astype(np.float32), target_c, float(score.item())

        finally:
            fwd_handle.remove()
            bwd_handle.remove()
            if was_training:
                self.model.train()

    def generate_aligned_cam(
        self,
        raw_image_bytes: bytes,
        eval_transform: Any,
        prep_config: PreprocessingConfig,
        device: torch.device,
        target_class: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Executes end-to-end Grad-CAM on original retinal image bytes:
        1. Decodes and transposes original image.
        2. Detects retinal FOV bounding box.
        3. Letterbox resizes to model input dimensions (512x512).
        4. Performs Grad-CAM backprop through EfficientNet-B0.
        5. Un-letterboxes and reverse-projects CAM to the exact original image resolution.
        6. Generates transparent heatmap PNG and blended overlay PNG artifacts.
        """
        with Image.open(io.BytesIO(raw_image_bytes)) as pil_img:
            pil_img.load()
            transposed = ImageOps.exif_transpose(pil_img)
            rgb_pil = _convert_image_to_rgb_safely(transposed)
            orig_rgb = np.asarray(rgb_pil, dtype=np.uint8)

        h_orig, w_orig = orig_rgb.shape[:2]

        # 1. FOV detection
        bbox, _diag, err_reason = detect_retinal_fov_bbox(orig_rgb, prep_config)
        if err_reason is not None or bbox is None:
            raise ValueError(f"Cannot generate Grad-CAM for ungradable image: {err_reason}")

        x1, y1, x2, y2 = bbox
        cropped = orig_rgb[y1:y2, x1:x2]

        # 2. Letterbox resize to input size (512x512)
        target_size = prep_config.target_size[0]
        padded_rgb, scale, (pad_t, pad_b, pad_l, pad_r), _ = _resize_preserving_aspect_ratio_letterbox_cv(
            cropped,
            target_size,
            target_size,
            down_interp=prep_config.downscale_interpolation,
            up_interp=prep_config.upscale_interpolation,
        )

        # 3. Model forward and backward
        tensor = eval_transform(Image.fromarray(padded_rgb, mode="RGB")).unsqueeze(0).to(device)
        cam_raw, chosen_class, raw_score = self.compute_cam(tensor, target_class=target_class)

        # 4. Upsample 16x16 CAM to 512x512
        cam_512 = cv2.resize(cam_raw, (target_size, target_size), interpolation=cv2.INTER_LINEAR)

        # 5. Reverse letterbox: crop out the scaled retinal region
        valid_h = target_size - pad_t - pad_b
        valid_w = target_size - pad_l - pad_r
        cam_unpadded = cam_512[pad_t : pad_t + valid_h, pad_l : pad_l + valid_w]

        # 6. Resize back to cropped retinal bounding box
        crop_h, crop_w = y2 - y1, x2 - x1
        cam_cropped = cv2.resize(cam_unpadded, (crop_w, crop_h), interpolation=cv2.INTER_LINEAR)

        # 7. Reverse FOV crop: place into original resolution canvas
        cam_full = np.zeros((h_orig, w_orig), dtype=np.float32)
        cam_full[y1:y2, x1:x2] = cam_cropped
        cam_full = np.clip(cam_full, 0.0, 1.0)

        # 8. Render artifacts
        heatmap_rgba_bytes, overlay_rgb_bytes = self._render_visual_artifacts(orig_rgb, cam_full)

        return {
            "target_class": chosen_class,
            "target_class_label": CLASS_INDEX_TO_LABEL.get(chosen_class, f"Grade_{chosen_class}"),
            "raw_score": raw_score,
            "model_layer": self.layer_name,
            "original_width": w_orig,
            "original_height": h_orig,
            "crop_bbox": (x1, y1, x2, y2),
            "cam_full": cam_full,
            "heatmap_png_bytes": heatmap_rgba_bytes,
            "overlay_png_bytes": overlay_rgb_bytes,
        }

    @staticmethod
    def _render_visual_artifacts(
        orig_rgb: np.ndarray,
        cam_full: np.ndarray,
    ) -> Tuple[bytes, bytes]:
        """
        Renders two clean artifacts:
        1. Transparent Heatmap PNG (RGBA): transparent for low attention, vivid jet/turbo for hotspots.
        2. Blended Overlay PNG (RGB): original retinal image blended with the heatmap.
        """
        # Apply standard medical JET colormap (blue -> cyan -> yellow -> red)
        cam_uint8 = np.uint8(255 * cam_full)
        heatmap_bgr = cv2.applyColorMap(cam_uint8, cv2.COLORMAP_JET)
        heatmap_rgb = cv2.cvtColor(heatmap_bgr, cv2.COLOR_BGR2RGB)

        # Compute smooth alpha channel: zero alpha for background (<0.08), increasing to 0.75 for hotspots
        alpha = np.clip((cam_full - 0.08) / 0.92, 0.0, 1.0) * 0.75
        alpha_uint8 = np.uint8(255 * alpha)

        rgba_img = np.dstack([heatmap_rgb, alpha_uint8])
        buf_heatmap = io.BytesIO()
        Image.fromarray(rgba_img, mode="RGBA").save(buf_heatmap, format="PNG", optimize=True)
        heatmap_bytes = buf_heatmap.getvalue()

        # Blended RGB overlay (65% retinal fundus + 35% heatmap where attention > 0.05)
        blend_mask = (cam_full[:, :, np.newaxis] > 0.05).astype(np.float32)
        weight = np.clip(cam_full[:, :, np.newaxis] * 0.5, 0.15, 0.45) * blend_mask
        blended = (1.0 - weight) * orig_rgb.astype(np.float32) + weight * heatmap_rgb.astype(np.float32)
        blended = np.clip(blended, 0, 255).astype(np.uint8)

        buf_overlay = io.BytesIO()
        Image.fromarray(blended, mode="RGB").save(buf_overlay, format="PNG", optimize=True)
        overlay_bytes = buf_overlay.getvalue()

        return heatmap_bytes, overlay_bytes

