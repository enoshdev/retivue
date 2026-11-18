"""Atomic checkpoint persistence, SHA-256 integrity checks, and full experiment provenance."""

import hashlib
import json
import os
import platform
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import torch

from ai.config import CLASS_INDEX_TO_LABEL, TrainingConfig


def compute_checkpoint_sha256(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def collect_environment_metadata() -> Dict[str, Any]:
    """Capture dependency versions and host platform metadata cleanly for experiment reproducibility."""
    import numpy
    import PIL
    import sklearn
    import torchvision

    xpu_avail = bool(hasattr(torch, "xpu") and torch.xpu.is_available())
    cuda_avail = bool(torch.cuda.is_available())
    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "torch_version": torch.__version__,
        "torchvision_version": torchvision.__version__,
        "numpy_version": numpy.__version__,
        "pillow_version": PIL.__version__,
        "sklearn_version": sklearn.__version__,
        "cuda_available": cuda_avail,
        "xpu_available": xpu_avail,
        "xpu_device_name": str(torch.xpu.get_device_name(0)) if xpu_avail else None,
        "cpu_threads": os.cpu_count(),
    }


def save_checkpoint_with_provenance(
    checkpoint_path: Path,
    model_state_dict: Dict[str, Any],
    optimizer_state_dict: Optional[Dict[str, Any]],
    scheduler_state_dict: Optional[Dict[str, Any]],
    epoch: int,
    stage: str,
    best_metric_name: str,
    best_metric_value: float,
    config: TrainingConfig,
    split_manifest_sha256: str,
    val_metrics_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Atomically write PyTorch checkpoint + JSON provenance sidecar with SHA-256 checksum."""
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    mean, std = config.get_normalization_stats()

    payload = {
        "model_state_dict": model_state_dict,
        "optimizer_state_dict": optimizer_state_dict,
        "scheduler_state_dict": scheduler_state_dict,
        "epoch": epoch,
        "stage": stage,
        "best_metric_name": best_metric_name,
        "best_metric_value": best_metric_value,
        "architecture": config.architecture,
        "num_classes": config.num_classes,
        "dropout_p": config.dropout_p,
        "input_size": config.input_size,
        "normalization_mode": config.normalization_mode,
        "norm_mean": list(mean),
        "norm_std": list(std),
        "class_mapping": dict(config.class_mapping or CLASS_INDEX_TO_LABEL),
        "split_manifest_sha256": split_manifest_sha256,
        "seed": config.seed,
        "saved_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    tmp_path = checkpoint_path.parent / f".tmp_{checkpoint_path.stem}_{uuid.uuid4().hex[:8]}.pt"
    try:
        torch.save(payload, tmp_path)
        os.replace(tmp_path, checkpoint_path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)

    ckpt_sha256 = compute_checkpoint_sha256(checkpoint_path)
    sidecar = {
        "checkpoint_path": str(checkpoint_path),
        "checkpoint_sha256": ckpt_sha256,
        "file_size_bytes": checkpoint_path.stat().st_size,
        "saved_at_utc": payload["saved_at_utc"],
        "epoch": epoch,
        "stage": stage,
        "best_metric_name": best_metric_name,
        "best_metric_value": best_metric_value,
        "split_manifest_sha256": split_manifest_sha256,
        "training_config": config.to_dict(),
        "environment": collect_environment_metadata(),
        "val_metrics_snapshot": val_metrics_snapshot,
    }

    meta_path = checkpoint_path.with_name(f"{checkpoint_path.stem}_meta.json")
    with open(meta_path, "w", encoding="utf-8") as mf:
        json.dump(sidecar, mf, indent=2)

    return sidecar


def verify_and_load_checkpoint(
    checkpoint_path: Path,
    expected_sha256: Optional[str] = None,
    map_location: str = "cpu",
) -> Dict[str, Any]:
    """Verify checkpoint exists, check optional SHA-256 integrity, and load safely onto map_location."""
    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Checkpoint file not found: '{checkpoint_path}'.")
    actual_sha = compute_checkpoint_sha256(checkpoint_path)
    if expected_sha256 and actual_sha.lower() != expected_sha256.strip().lower():
        raise ValueError(
            f"Checkpoint SHA-256 mismatch for '{checkpoint_path}': expected {expected_sha256}, got {actual_sha}."
        )
    # Note: weights_only=False required strictly for internal metadata dicts alongside tensors
    loaded = torch.load(checkpoint_path, map_location=map_location, weights_only=False)
    loaded["_verified_sha256"] = actual_sha
    return loaded
