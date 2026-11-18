"""Model factory and backbone freeze/unfreeze helpers for 5-class DR classification."""

from typing import Optional, Tuple

import torch.nn as nn
from torchvision import models


SUPPORTED_ARCHITECTURES = ("efficientnet_b0", "resnet50")


def build_classifier_model(
    architecture: str = "efficientnet_b0",
    num_classes: int = 5,
    pretrained: bool = True,
    dropout_p: float = 0.3,
) -> nn.Module:
    """
    Instantiate a pretrained or fresh CNN backbone with a 5-class DR classification head.
    """
    arch = (architecture or "").strip().lower()
    if arch == "efficientnet_b0":
        weights = models.EfficientNet_B0_Weights.DEFAULT if pretrained else None
        model = models.efficientnet_b0(weights=weights)
        in_features = model.classifier[1].in_features
        model.classifier = nn.Sequential(
            nn.Dropout(p=dropout_p, inplace=True),
            nn.Linear(in_features, num_classes),
        )
        return model

    if arch == "resnet50":
        weights = models.ResNet50_Weights.DEFAULT if pretrained else None
        model = models.resnet50(weights=weights)
        in_features = model.fc.in_features
        model.fc = nn.Sequential(
            nn.Dropout(p=dropout_p),
            nn.Linear(in_features, num_classes),
        )
        return model

    raise ValueError(
        f"Unsupported model architecture '{architecture}'. Supported: {SUPPORTED_ARCHITECTURES}."
    )


def set_backbone_trainable(
    model: nn.Module,
    architecture: str,
    trainable: bool,
    unfreeze_from_block: Optional[int] = None,
) -> None:
    """
    Freeze or unfreeze backbone feature layers while always keeping the classifier head trainable.
    When unfreeze_from_block is provided for EfficientNet-B0 (e.g. 5), keep early low-level edge
    stages frozen and fine-tune upper semantic stages (~92.3% of weights) for faster CPU convergence.
    """
    arch = (architecture or "").strip().lower()
    head_prefix = "classifier" if arch == "efficientnet_b0" else "fc"
    for name, param in model.named_parameters():
        if name.startswith(head_prefix):
            param.requires_grad = True
        elif not trainable:
            param.requires_grad = False
        elif arch == "efficientnet_b0" and unfreeze_from_block is not None and name.startswith("features."):
            parts = name.split(".")
            block_idx = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
            param.requires_grad = block_idx >= unfreeze_from_block
        else:
            param.requires_grad = True


def count_parameters(model: nn.Module) -> Tuple[int, int]:
    """Return (total_parameters, trainable_parameters)."""
    total = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    return int(total), int(trainable)
