"""Phase 9 AI configuration, hardware device detection, seeding, and model storage layout."""

import os
import random
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from app.core.config import settings
from data_pipeline.label_mapping import DR_CANDIDATE_SCHEME


CLASS_INDEX_TO_LABEL: Dict[int, str] = dict(DR_CANDIDATE_SCHEME)
LABEL_TO_CLASS_INDEX: Dict[str, int] = {v: k for k, v in CLASS_INDEX_TO_LABEL.items()}

IMAGENET_MEAN: Tuple[float, float, float] = (0.485, 0.456, 0.406)
IMAGENET_STD: Tuple[float, float, float] = (0.229, 0.224, 0.225)
APTOS_TRAIN_MEAN: Tuple[float, float, float] = (0.390261, 0.209356, 0.066498)
APTOS_TRAIN_STD: Tuple[float, float, float] = (0.287072, 0.157607, 0.079566)


class ModelDirectoryError(Exception):
    """Raised when MODEL_ROOT resolution conflicts with forbidden workspace paths or permissions."""


@dataclass(frozen=True)
class TrainingConfig:
    experiment_name: str = "aptos_effnet_b0_baseline"
    dataset_name: str = "aptos"
    architecture: str = "efficientnet_b0"  # 'efficientnet_b0' or 'resnet50'
    num_classes: int = 5
    pretrained: bool = True
    seed: int = 42
    device_preference: str = "auto"  # 'auto', 'xpu', 'cuda', 'cpu'
    input_size: int = 512
    batch_size: int = 16
    grad_accum_steps: int = 2
    num_workers: int = 0
    warmup_epochs: int = 3
    max_epochs: int = 15
    warmup_lr: float = 1e-3
    finetune_lr: float = 1e-4
    weight_decay: float = 1e-4
    grad_clip_norm: float = 2.0
    dropout_p: float = 0.3
    early_stopping_patience: int = 5
    unfreeze_from_block: Optional[int] = None  # Optional partial Stage-2 unfreeze (e.g. 5 -> EfficientNet features[5:])
    imbalance_strategy: str = "unweighted"  # 'unweighted', 'weighted_loss_effective', 'weighted_loss_sqrt_inv', 'weighted_sampler'
    normalization_mode: str = "imagenet"  # 'imagenet' or 'aptos_train'
    augmentation_enabled: bool = True
    clahe_applied: bool = False
    deterministic_mode: bool = True
    class_mapping: Dict[int, str] = field(default_factory=lambda: dict(CLASS_INDEX_TO_LABEL))

    def get_normalization_stats(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
        if self.normalization_mode == "aptos_train":
            return APTOS_TRAIN_MEAN, APTOS_TRAIN_STD
        return IMAGENET_MEAN, IMAGENET_STD

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        mean, std = self.get_normalization_stats()
        data["resolved_norm_mean"] = list(mean)
        data["resolved_norm_std"] = list(std)
        return data


def get_safe_model_root(root_override: Optional[str] = None) -> Path:
    """Validate and create MODEL_ROOT outside Git workspace, public assets, and clinical patient storage."""
    raw = root_override or settings.MODEL_ROOT
    if not raw or not str(raw).strip():
        raise ModelDirectoryError("MODEL_ROOT cannot be empty.")
    root = Path(raw).resolve()

    repo_root = Path(__file__).resolve().parent.parent.parent
    forbidden = (
        ("clinical patient storage", Path(settings.LOCAL_STORAGE_ROOT).resolve()),
        ("Next.js public directory", (repo_root / "public").resolve()),
        ("frontend src directory", (repo_root / "src").resolve()),
        ("Git workspace root", repo_root.resolve()),
    )
    for label, fpath in forbidden:
        if root == fpath or fpath in root.parents or root in fpath.parents:
            raise ModelDirectoryError(f"MODEL_ROOT '{root}' overlaps {label} '{fpath}'.")

    (root / "experiments").mkdir(parents=True, exist_ok=True)
    if not os.access(root, os.W_OK):
        raise ModelDirectoryError(f"MODEL_ROOT '{root}' is not writable.")
    return root


def seed_everything(seed: int, deterministic: bool = True) -> None:
    """Set Python, NumPy, and PyTorch random seeds cleanly for reproducible runs."""
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    if hasattr(torch, "xpu") and torch.xpu.is_available():
        torch.xpu.manual_seed_all(seed)
    if deterministic:
        try:
            torch.use_deterministic_algorithms(True, warn_only=True)
        except Exception:
            pass


def _smoke_test_device_ops(device_str: str) -> Tuple[bool, str]:
    """
    Run a tiny Conv2d + backward smoke pass in an isolated subprocess before committing to an
    accelerator so native C++ driver aborts (e.g., older Intel Arc Level-Zero drivers) fall back
    safely to CPU without terminating the parent process.
    """
    probe_code = (
        "import torch; "
        f"dev = torch.device({device_str!r}); "
        "conv = torch.nn.Conv2d(3, 8, kernel_size=3, padding=1).to(dev); "
        "x = torch.randn(2, 3, 32, 32, device=dev); "
        "out = conv(x).sum(); "
        "out.backward(); "
        "assert torch.isfinite(out.detach().cpu()).all(), 'non-finite output'; "
        "print('SMOKE_OK')"
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", probe_code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if proc.returncode == 0 and "SMOKE_OK" in proc.stdout:
            return True, f"Verified forward/backward kernel execution on '{device_str}'."
        detail = (proc.stderr or proc.stdout or "").strip().splitlines()[-1:] or ["no stderr"]
        return (
            False,
            f"Device '{device_str}' kernel check failed in isolated probe (exit={proc.returncode}: {detail[0]}).",
        )
    except Exception as exc:
        return False, f"Device '{device_str}' kernel probe failed: {exc.__class__.__name__}: {exc}"


def resolve_torch_device(preference: str = "auto") -> Dict[str, Any]:
    """
    Resolve compute device cleanly ('cuda', 'xpu', or 'cpu'), running a crash-isolated kernel check
    on accelerators before committing to them so older iGPU drivers fall back safely to CPU.
    """
    import torch

    pref = (preference or "auto").strip().lower()
    candidates: List[str] = []
    if pref == "auto":
        if torch.cuda.is_available():
            candidates.append("cuda")
        if hasattr(torch, "xpu") and torch.xpu.is_available():
            candidates.append("xpu")
        candidates.append("cpu")
    else:
        candidates.append(pref)
        if pref != "cpu":
            candidates.append("cpu")

    notes: List[str] = []
    for cand in candidates:
        if cand == "cpu":
            cpu_threads = os.cpu_count() or 1
            torch.set_num_threads(cpu_threads)
            notes.append(f"Selected CPU backend ({cpu_threads} logical threads).")
            return {
                "device": "cpu",
                "device_name": "CPU",
                "diagnostics": notes,
            }
        ok, msg = _smoke_test_device_ops(cand)
        notes.append(msg)
        if ok:
            dev_name = cand
            if cand == "xpu" and hasattr(torch, "xpu"):
                dev_name = str(torch.xpu.get_device_name(0))
            elif cand == "cuda":
                dev_name = str(torch.cuda.get_device_name(0))
            return {
                "device": cand,
                "device_name": dev_name,
                "diagnostics": notes,
            }

    cpu_threads = os.cpu_count() or 1
    torch.set_num_threads(cpu_threads)
    return {
        "device": "cpu",
        "device_name": "CPU",
        "diagnostics": notes,
    }
