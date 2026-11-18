"""Retinal field-of-view detection, usability quality gates, aspect-preserving preprocessing, and provenance logging."""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np
from PIL import Image, ImageFile, ImageOps, UnidentifiedImageError

from data_pipeline.manifest import ManifestRecord

# Never silently load truncated image streams
ImageFile.LOAD_TRUNCATED_IMAGES = False


@dataclass(frozen=True)
class PreprocessingConfig:
    apply_exif_orientation: bool = True
    target_mode: str = "RGB"
    target_size: Optional[Tuple[int, int]] = None  # (width, height) letterbox square canvas
    output_format: str = "PNG"
    # Phase 8 Retinal Field-of-View & Quality Control configuration (opt-in so Phase 5 defaults stay unchanged)
    crop_fov: bool = False
    fov_threshold: int = 12
    fov_max_bg_threshold: int = 24
    fov_pad_ratio: float = 0.015
    min_fov_area_ratio: float = 0.12
    min_crop_dim: int = 64
    quality_check_enabled: bool = False
    min_image_std: float = 4.0
    min_fov_std: float = 5.0
    min_fov_brightness: float = 12.0
    max_saturated_fraction: float = 0.70
    # Phase 11 hardened extended quality diagnostics (opt-in preset for inference & external eval)
    extended_quality_check_enabled: bool = False
    min_laplacian_variance: float = 15.0
    min_local_rms_contrast: float = 1.0
    max_fov_aspect_ratio: float = 1.65
    quality_eval_max_dim: int = 512
    # Interpolation & Enhancement configuration (enhancement off by default)
    downscale_interpolation: str = "INTER_AREA"
    upscale_interpolation: str = "INTER_CUBIC"
    clahe_applied: bool = False
    clahe_clip_limit: float = 2.0
    clahe_tile_grid: Tuple[int, int] = (8, 8)
    color_enhancement_applied: bool = False
    model_normalization_applied: bool = False
    pixel_normalization_policy: Dict[str, Any] = field(
        default_factory=lambda: {
            "disk_pixel_dtype": "uint8_0_to_255",
            "training_rescale": "divide_by_255_to_0_1",
            "normalize_using_train_split_stats": True,
            "clahe_default": False,
        }
    )

    @classmethod
    def phase8_aptos_preset(
        cls,
        target_size: Tuple[int, int] = (512, 512),
        clahe_applied: bool = False,
    ) -> "PreprocessingConfig":
        """Documented Phase 8 APTOS retinal FOV cropping + aspect-preserving preprocessing preset."""
        return cls(
            apply_exif_orientation=True,
            target_mode="RGB",
            target_size=target_size,
            output_format="PNG",
            crop_fov=True,
            fov_threshold=12,
            fov_max_bg_threshold=24,
            fov_pad_ratio=0.015,
            min_fov_area_ratio=0.12,
            min_crop_dim=64,
            quality_check_enabled=True,
            min_image_std=4.0,
            min_fov_std=5.0,
            min_fov_brightness=12.0,
            max_saturated_fraction=0.70,
            downscale_interpolation="INTER_AREA",
            upscale_interpolation="INTER_CUBIC",
            clahe_applied=clahe_applied,
            color_enhancement_applied=clahe_applied,
            model_normalization_applied=False,
        )

    @classmethod
    def phase11_hardened_preset(
        cls,
        target_size: Tuple[int, int] = (512, 512),
        clahe_applied: bool = False,
    ) -> "PreprocessingConfig":
        """Phase 11 hardened quality-gating preset (adds standardized <=512px sharpness, local contrast, and aspect gates)."""
        return cls(
            apply_exif_orientation=True,
            target_mode="RGB",
            target_size=target_size,
            output_format="PNG",
            crop_fov=True,
            fov_threshold=12,
            fov_max_bg_threshold=24,
            fov_pad_ratio=0.015,
            min_fov_area_ratio=0.12,
            min_crop_dim=64,
            quality_check_enabled=True,
            min_image_std=4.0,
            min_fov_std=5.0,
            min_fov_brightness=12.0,
            max_saturated_fraction=0.70,
            extended_quality_check_enabled=True,
            min_laplacian_variance=15.0,
            min_local_rms_contrast=1.0,
            max_fov_aspect_ratio=1.65,
            quality_eval_max_dim=512,
            downscale_interpolation="INTER_AREA",
            upscale_interpolation="INTER_CUBIC",
            clahe_applied=clahe_applied,
            color_enhancement_applied=clahe_applied,
            model_normalization_applied=False,
        )


@dataclass(frozen=True)
class PreprocessingRecord:
    dataset_name: str
    source_relative_path: str
    source_sha256: str
    processed_relative_path: Optional[str]
    processed_sha256: Optional[str]
    status: str  # 'processed', 'flagged_quality', 'flagged_fov_crop', 'decode_error', 'missing_source'
    flag_reason: Optional[str]
    original_width: int
    original_height: int
    original_mode: str
    fov_crop_applied: bool
    crop_bbox_x1: int
    crop_bbox_y1: int
    crop_bbox_x2: int
    crop_bbox_y2: int
    cropped_width: int
    cropped_height: int
    processed_width: int
    processed_height: int
    processed_mode: str
    exif_orientation_transposed: bool
    aspect_ratio_preserved: bool
    interpolation_used: str
    scale_factor: float
    pad_left: int
    pad_top: int
    pad_right: int
    pad_bottom: int
    fov_active_mean_intensity: float
    fov_active_std_intensity: float
    fov_area_ratio: float
    output_format: str


def _convert_image_to_rgb_safely(img: Image.Image) -> Image.Image:
    """Convert grayscale, palette, RGBA, CMYK, or 16-bit images cleanly over black background."""
    if img.mode == "RGB":
        return img
    if img.mode in ("RGBA", "LA", "PA"):
        rgba = img.convert("RGBA")
        black_bg = Image.new("RGB", rgba.size, (0, 0, 0))
        black_bg.paste(rgba, mask=rgba.split()[3])
        return black_bg
    return img.convert("RGB")


def evaluate_extended_retinal_quality(
    roi_rgb: np.ndarray,
    bg_thresh: int = 12,
    eval_max_dim: int = 512,
    min_laplacian_variance: float = 15.0,
    min_local_rms_contrast: float = 1.0,
    max_fov_aspect_ratio: float = 1.65,
) -> Tuple[Dict[str, float], List[str]]:
    """
    Evaluate blur (Laplacian variance), local 15x15 RMS contrast, and FOV asymmetry
    after downscaling crops larger than `eval_max_dim` via INTER_AREA for multi-camera invariance.
    """
    ch, cw = roi_rgb.shape[:2]
    aspect_ratio = max(float(cw) / float(max(1, ch)), float(ch) / float(max(1, cw)))

    if max(cw, ch) > eval_max_dim:
        scale = float(eval_max_dim) / float(max(cw, ch))
        ew = max(1, int(round(cw * scale)))
        eh = max(1, int(round(ch * scale)))
        eval_roi = cv2.resize(roi_rgb, (ew, eh), interpolation=cv2.INTER_AREA)
    else:
        eval_roi = roi_rgb

    gray_eval = cv2.cvtColor(eval_roi, cv2.COLOR_RGB2GRAY)
    lum_eval = np.max(eval_roi, axis=2)
    act_mask = lum_eval > bg_thresh

    lap = cv2.Laplacian(gray_eval, cv2.CV_64F)
    lap_vals = lap[act_mask] if np.any(act_mask) else lap.ravel()
    lap_var = float(np.var(lap_vals))

    gray_f = gray_eval.astype(np.float64)
    local_mean = cv2.GaussianBlur(gray_f, (15, 15), 0)
    local_sq = cv2.GaussianBlur(gray_f * gray_f, (15, 15), 0)
    local_std_map = np.sqrt(np.maximum(0.0, local_sq - local_mean * local_mean))
    act_local_stds = local_std_map[act_mask] if np.any(act_mask) else local_std_map.ravel()
    local_rms_contrast = float(np.median(act_local_stds))

    reasons: List[str] = []
    if aspect_ratio > max_fov_aspect_ratio:
        reasons.append(f"fov_asymmetric_obstruction (aspect_ratio={aspect_ratio:.2f} > {max_fov_aspect_ratio})")
    if lap_var < min_laplacian_variance:
        reasons.append(f"blur_low_sharpness (laplacian_var={lap_var:.2f} < {min_laplacian_variance})")
    if local_rms_contrast < min_local_rms_contrast:
        reasons.append(f"low_local_contrast (local_rms={local_rms_contrast:.2f} < {min_local_rms_contrast})")

    metrics = {
        "fov_aspect_ratio": round(aspect_ratio, 4),
        "laplacian_variance": round(lap_var, 4),
        "local_rms_contrast": round(local_rms_contrast, 4),
    }
    return metrics, reasons


def detect_retinal_fov_bbox(
    rgb_arr: np.ndarray,
    config: PreprocessingConfig,
) -> Tuple[Optional[Tuple[int, int, int, int]], Dict[str, float], Optional[str]]:
    """
    Detect the bounding box (x1, y1, x2, y2) of the largest connected retinal tissue region
    using maximum RGB intensity to avoid truncating dim peripheral retina or optic disc margins.
    Returns (bbox, quality_metrics, failure_reason). Never fabricates a crop on invalid images.
    """
    h, w = rgb_arr.shape[:2]
    full_std = float(np.std(rgb_arr))
    if config.quality_check_enabled and full_std < config.min_image_std:
        return (
            None,
            {"fov_active_mean": 0.0, "fov_active_std": full_std, "fov_area_ratio": 0.0},
            f"Blank or near-constant image (std={full_std:.2f} < {config.min_image_std}).",
        )

    # Max channel intensity preserves deep-red peripheral retinal edge over dark background
    lum = np.max(rgb_arr, axis=2)

    # Sample small 8x8 corners to estimate camera letterbox darkness without touching central retina
    patch = max(4, min(16, min(h, w) // 20))
    corners = [
        lum[:patch, :patch],
        lum[:patch, w - patch :],
        lum[h - patch :, :patch],
        lum[h - patch :, w - patch :],
    ]
    min_corner_med = min(float(np.median(c)) for c in corners)
    bg_thresh = (
        min(config.fov_max_bg_threshold, max(config.fov_threshold, int(round(min_corner_med)) + 6))
        if min_corner_med < 25.0
        else config.fov_threshold
    )

    fg_mask = (lum > bg_thresh).astype(np.uint8)
    # Close tiny internal dark lesions/vessels; ignore tiny stray corner watermarks via largest component
    k_size = max(3, (min(h, w) // 250) | 1)
    kernel = np.ones((k_size, k_size), dtype=np.uint8)
    fg_closed = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel)

    num_labels, _labels, stats, _ = cv2.connectedComponentsWithStats(fg_closed, connectivity=8)
    if num_labels <= 1:
        return (
            None,
            {"fov_active_mean": 0.0, "fov_active_std": 0.0, "fov_area_ratio": 0.0},
            "Retinal FOV detection failed: zero foreground pixels above background threshold.",
        )

    areas = stats[1:, cv2.CC_STAT_AREA]
    best_idx = int(np.argmax(areas)) + 1
    x = int(stats[best_idx, cv2.CC_STAT_LEFT])
    y = int(stats[best_idx, cv2.CC_STAT_TOP])
    bw = int(stats[best_idx, cv2.CC_STAT_WIDTH])
    bh = int(stats[best_idx, cv2.CC_STAT_HEIGHT])

    # Apply safety padding margin so optic disc edges / peripheral retina are never clipped
    pad_x = int(round(bw * config.fov_pad_ratio))
    pad_y = int(round(bh * config.fov_pad_ratio))
    x1 = max(0, x - pad_x)
    y1 = max(0, y - pad_y)
    x2 = min(w, x + bw + pad_x)
    y2 = min(h, y + bh + pad_y)

    crop_w = x2 - x1
    crop_h = y2 - y1
    area_ratio = float(crop_w * crop_h) / float(w * h)

    if crop_w < config.min_crop_dim or crop_h < config.min_crop_dim or area_ratio < config.min_fov_area_ratio:
        return (
            None,
            {"fov_active_mean": 0.0, "fov_active_std": 0.0, "fov_area_ratio": round(area_ratio, 4)},
            (
                f"Retinal FOV bounding box ({crop_w}x{crop_h}, area_ratio={area_ratio:.3f}) "
                f"below safety minimum ({config.min_crop_dim}px, ratio>={config.min_fov_area_ratio})."
            ),
        )

    # Evaluate usability metrics strictly on active retinal tissue pixels inside bbox
    cropped_rgb = rgb_arr[y1:y2, x1:x2]
    cropped_lum = lum[y1:y2, x1:x2]
    active_pixels = cropped_rgb[cropped_lum > bg_thresh]
    if active_pixels.size == 0:
        return (
            None,
            {"fov_active_mean": 0.0, "fov_active_std": 0.0, "fov_area_ratio": round(area_ratio, 4)},
            "Detected FOV contains zero active tissue pixels.",
        )

    active_mean = float(np.mean(active_pixels))
    active_std = float(np.std(active_pixels))
    sat_frac = float(np.mean(cropped_lum[cropped_lum > bg_thresh] >= 250))

    metrics = {
        "fov_active_mean": round(active_mean, 3),
        "fov_active_std": round(active_std, 3),
        "fov_area_ratio": round(area_ratio, 4),
    }

    if config.quality_check_enabled:
        if active_std < config.min_fov_std:
            return None, metrics, f"Retinal FOV has near-zero tissue contrast (std={active_std:.2f})."
        if active_mean < config.min_fov_brightness:
            return None, metrics, f"Excessively dark unusable retinal image (mean={active_mean:.2f} < {config.min_fov_brightness})."
        if sat_frac > config.max_saturated_fraction:
            return None, metrics, f"Excessively bright / washed-out retinal image (sat_frac={sat_frac:.2f} > {config.max_saturated_fraction})."
        if config.extended_quality_check_enabled:
            ext_metrics, ext_reasons = evaluate_extended_retinal_quality(
                cropped_rgb,
                bg_thresh=bg_thresh,
                eval_max_dim=config.quality_eval_max_dim,
                min_laplacian_variance=config.min_laplacian_variance,
                min_local_rms_contrast=config.min_local_rms_contrast,
                max_fov_aspect_ratio=config.max_fov_aspect_ratio,
            )
            metrics.update(ext_metrics)
            if ext_reasons:
                return None, metrics, f"Extended quality gate rejected image: {'; '.join(ext_reasons)}."

    return (x1, y1, x2, y2), metrics, None


def _resize_preserving_aspect_ratio_letterbox_cv(
    rgb_arr: np.ndarray,
    target_w: int,
    target_h: int,
    down_interp: str = "INTER_AREA",
    up_interp: str = "INTER_CUBIC",
) -> Tuple[np.ndarray, float, Tuple[int, int, int, int], str]:
    """
    Resize RGB numpy array preserving exact original aspect ratio via centered zero-padding.
    Selects explicit anti-aliased interpolation for downscaling and bicubic for upscaling.
    """
    src_h, src_w = rgb_arr.shape[:2]
    scale = min(target_w / src_w, target_h / src_h)
    new_w = max(1, int(round(src_w * scale)))
    new_h = max(1, int(round(src_h * scale)))

    interp_map = {
        "INTER_AREA": cv2.INTER_AREA,
        "INTER_CUBIC": cv2.INTER_CUBIC,
        "INTER_LINEAR": cv2.INTER_LINEAR,
        "INTER_LANCZOS4": cv2.INTER_LANCZOS4,
    }
    if scale < 1.0:
        interp_name = down_interp
    else:
        interp_name = up_interp
    cv_interp = interp_map.get(interp_name, cv2.INTER_AREA)

    if (new_w, new_h) != (src_w, src_h):
        resized = cv2.resize(rgb_arr, (new_w, new_h), interpolation=cv_interp)
    else:
        resized = rgb_arr

    canvas = np.zeros((target_h, target_w, 3), dtype=np.uint8)
    pad_left = (target_w - new_w) // 2
    pad_top = (target_h - new_h) // 2
    pad_right = target_w - new_w - pad_left
    pad_bottom = target_h - new_h - pad_top

    canvas[pad_top : pad_top + new_h, pad_left : pad_left + new_w] = resized
    return canvas, round(scale, 6), (pad_left, pad_top, pad_right, pad_bottom), interp_name


class DatasetPreprocessor:
    """
    Deterministic, aspect-ratio-preserving retinal preprocessing pipeline writing strictly
    into datasets/processed/<dataset>/ without ever altering or deleting raw originals.
    """

    def __init__(self, config: Optional[PreprocessingConfig] = None) -> None:
        self.config = config or PreprocessingConfig()

    def preprocess_single(
        self,
        dataset_name: str,
        relative_path: str,
        source_sha256: str,
        raw_dataset_dir: Path,
        processed_dataset_dir: Path,
    ) -> Tuple[PreprocessingRecord, Optional[np.ndarray]]:
        """Decode, validate, optionally FOV-crop, letterbox-resize, and write one processed PNG."""
        src_path = (raw_dataset_dir / relative_path).resolve()
        ext = ".png" if self.config.output_format.upper() == "PNG" else ".jpg"
        out_rel = Path(f"{Path(relative_path).with_suffix('').as_posix()}{ext}")

        if not src_path.is_file():
            return (
                PreprocessingRecord(
                    dataset_name=dataset_name,
                    source_relative_path=relative_path,
                    source_sha256=source_sha256,
                    processed_relative_path=None,
                    processed_sha256=None,
                    status="missing_source",
                    flag_reason="Raw source file missing from disk.",
                    original_width=0,
                    original_height=0,
                    original_mode="",
                    fov_crop_applied=False,
                    crop_bbox_x1=0,
                    crop_bbox_y1=0,
                    crop_bbox_x2=0,
                    crop_bbox_y2=0,
                    cropped_width=0,
                    cropped_height=0,
                    processed_width=0,
                    processed_height=0,
                    processed_mode="",
                    exif_orientation_transposed=False,
                    aspect_ratio_preserved=True,
                    interpolation_used="",
                    scale_factor=1.0,
                    pad_left=0,
                    pad_top=0,
                    pad_right=0,
                    pad_bottom=0,
                    fov_active_mean_intensity=0.0,
                    fov_active_std_intensity=0.0,
                    fov_area_ratio=0.0,
                    output_format=self.config.output_format.upper(),
                ),
                None,
            )

        try:
            with Image.open(src_path) as img:
                img.load()
                orig_w, orig_h = img.size
                orig_mode = img.mode

                exif_transposed = False
                if self.config.apply_exif_orientation:
                    exif = img.getexif()
                    orientation = exif.get(274) if exif else None
                    if orientation and orientation != 1:
                        exif_transposed = True
                    work_img = ImageOps.exif_transpose(img)
                else:
                    work_img = img.copy()

                work_img = _convert_image_to_rgb_safely(work_img)
                rgb_arr = np.asarray(work_img, dtype=np.uint8)
        except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
            return (
                PreprocessingRecord(
                    dataset_name=dataset_name,
                    source_relative_path=relative_path,
                    source_sha256=source_sha256,
                    processed_relative_path=None,
                    processed_sha256=None,
                    status="decode_error",
                    flag_reason=f"Failed to decode raw image: {exc.__class__.__name__}",
                    original_width=0,
                    original_height=0,
                    original_mode="",
                    fov_crop_applied=False,
                    crop_bbox_x1=0,
                    crop_bbox_y1=0,
                    crop_bbox_x2=0,
                    crop_bbox_y2=0,
                    cropped_width=0,
                    cropped_height=0,
                    processed_width=0,
                    processed_height=0,
                    processed_mode="",
                    exif_orientation_transposed=False,
                    aspect_ratio_preserved=True,
                    interpolation_used="",
                    scale_factor=1.0,
                    pad_left=0,
                    pad_top=0,
                    pad_right=0,
                    pad_bottom=0,
                    fov_active_mean_intensity=0.0,
                    fov_active_std_intensity=0.0,
                    fov_area_ratio=0.0,
                    output_format=self.config.output_format.upper(),
                ),
                None,
            )

        cur_h, cur_w = rgb_arr.shape[:2]
        x1, y1, x2, y2 = 0, 0, cur_w, cur_h
        metrics = {
            "fov_active_mean": round(float(np.mean(rgb_arr)), 3),
            "fov_active_std": round(float(np.std(rgb_arr)), 3),
            "fov_area_ratio": 1.0,
        }
        fov_crop_applied = False

        if self.config.crop_fov or self.config.quality_check_enabled:
            bbox, fov_metrics, err_reason = detect_retinal_fov_bbox(rgb_arr, self.config)
            metrics = fov_metrics
            if err_reason is not None or bbox is None:
                status = "flagged_quality" if ("dark" in (err_reason or "").lower() or "bright" in (err_reason or "").lower() or "blank" in (err_reason or "").lower() or "contrast" in (err_reason or "").lower()) else "flagged_fov_crop"
                return (
                    PreprocessingRecord(
                        dataset_name=dataset_name,
                        source_relative_path=relative_path,
                        source_sha256=source_sha256,
                        processed_relative_path=None,
                        processed_sha256=None,
                        status=status,
                        flag_reason=err_reason,
                        original_width=orig_w,
                        original_height=orig_h,
                        original_mode=orig_mode,
                        fov_crop_applied=False,
                        crop_bbox_x1=0,
                        crop_bbox_y1=0,
                        crop_bbox_x2=0,
                        crop_bbox_y2=0,
                        cropped_width=0,
                        cropped_height=0,
                        processed_width=0,
                        processed_height=0,
                        processed_mode="",
                        exif_orientation_transposed=exif_transposed,
                        aspect_ratio_preserved=True,
                        interpolation_used="",
                        scale_factor=1.0,
                        pad_left=0,
                        pad_top=0,
                        pad_right=0,
                        pad_bottom=0,
                        fov_active_mean_intensity=metrics["fov_active_mean"],
                        fov_active_std_intensity=metrics["fov_active_std"],
                        fov_area_ratio=metrics["fov_area_ratio"],
                        output_format=self.config.output_format.upper(),
                    ),
                    None,
                )
            if self.config.crop_fov:
                x1, y1, x2, y2 = bbox
                rgb_arr = rgb_arr[y1:y2, x1:x2]
                fov_crop_applied = True

        crop_h, crop_w = rgb_arr.shape[:2]
        scale_factor = 1.0
        pads = (0, 0, 0, 0)
        interp_used = "NONE_ORIGINAL_SIZE"

        if self.config.target_size is not None:
            tw, th = self.config.target_size
            rgb_arr, scale_factor, pads, interp_used = _resize_preserving_aspect_ratio_letterbox_cv(
                rgb_arr,
                tw,
                th,
                down_interp=self.config.downscale_interpolation,
                up_interp=self.config.upscale_interpolation,
            )

        # Optional reversible enhancement (strictly disabled by default)
        if self.config.clahe_applied:
            lab = cv2.cvtColor(rgb_arr, cv2.COLOR_RGB2LAB)
            l_chan, a_chan, b_chan = cv2.split(lab)
            clahe = cv2.createCLAHE(
                clipLimit=self.config.clahe_clip_limit,
                tileGridSize=self.config.clahe_tile_grid,
            )
            l_eq = clahe.apply(l_chan)
            rgb_arr = cv2.cvtColor(cv2.merge((l_eq, a_chan, b_chan)), cv2.COLOR_LAB2RGB)

        proc_h, proc_w = rgb_arr.shape[:2]
        out_abs = (processed_dataset_dir / out_rel).resolve()
        out_abs.parent.mkdir(parents=True, exist_ok=True)
        out_pil = Image.fromarray(rgb_arr, mode="RGB")

        save_kwargs = {"format": self.config.output_format.upper()}
        if save_kwargs["format"] == "JPEG":
            save_kwargs["quality"] = 95
        out_pil.save(out_abs, **save_kwargs)

        with open(out_abs, "rb") as pf:
            proc_sha = hashlib.sha256(pf.read()).hexdigest()

        rec = PreprocessingRecord(
            dataset_name=dataset_name,
            source_relative_path=relative_path,
            source_sha256=source_sha256,
            processed_relative_path=out_rel.as_posix(),
            processed_sha256=proc_sha,
            status="processed",
            flag_reason=None,
            original_width=orig_w,
            original_height=orig_h,
            original_mode=orig_mode,
            fov_crop_applied=fov_crop_applied,
            crop_bbox_x1=x1,
            crop_bbox_y1=y1,
            crop_bbox_x2=x2,
            crop_bbox_y2=y2,
            cropped_width=crop_w,
            cropped_height=crop_h,
            processed_width=proc_w,
            processed_height=proc_h,
            processed_mode="RGB",
            exif_orientation_transposed=exif_transposed,
            aspect_ratio_preserved=True,
            interpolation_used=interp_used,
            scale_factor=scale_factor,
            pad_left=pads[0],
            pad_top=pads[1],
            pad_right=pads[2],
            pad_bottom=pads[3],
            fov_active_mean_intensity=metrics["fov_active_mean"],
            fov_active_std_intensity=metrics["fov_active_std"],
            fov_area_ratio=metrics["fov_area_ratio"],
            output_format=self.config.output_format.upper(),
        )
        return rec, rgb_arr

    def run(
        self,
        dataset_name: str,
        records: List[ManifestRecord],
        raw_dataset_dir: Path,
        processed_dataset_dir: Path,
        manifests_dir: Path,
        log_filename: Optional[str] = None,
    ) -> Tuple[List[PreprocessingRecord], Path]:
        processed_dataset_dir.mkdir(parents=True, exist_ok=True)
        manifests_dir.mkdir(parents=True, exist_ok=True)

        accepted = sorted(
            [r for r in records if r.validation_status == "accepted"],
            key=lambda x: x.relative_path,
        )

        prep_records: List[PreprocessingRecord] = []
        for rec in accepted:
            pr, _ = self.preprocess_single(
                dataset_name=dataset_name,
                relative_path=rec.relative_path,
                source_sha256=rec.sha256_checksum or "",
                raw_dataset_dir=raw_dataset_dir,
                processed_dataset_dir=processed_dataset_dir,
            )
            prep_records.append(pr)

        log_path = manifests_dir / (log_filename or f"{dataset_name}_preprocessing_log.jsonl")
        with open(log_path, "w", encoding="utf-8") as lf:
            header_meta = {"_preprocessing_config": asdict(self.config)}
            lf.write(json.dumps(header_meta) + "\n")
            for pr in prep_records:
                lf.write(json.dumps(asdict(pr)) + "\n")

        return prep_records, log_path
