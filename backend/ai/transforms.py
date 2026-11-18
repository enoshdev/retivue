"""Clinically safe image transformations and normalization matching Phase 8 512x512 fundus crops."""

from typing import Tuple

from torchvision import transforms


def build_retinal_transforms(
    input_size: int,
    mean: Tuple[float, float, float],
    std: Tuple[float, float, float],
    is_train: bool,
    augmentation_enabled: bool = True,
) -> transforms.Compose:
    """
    Build deterministic evaluation or clinically conservative fundus training transforms.
    Avoids aspect-distorting warps, erasing/cutout over microaneurysms, and strong color shifts.
    """
    ops = [transforms.Resize((input_size, input_size))]

    if is_train and augmentation_enabled:
        ops.extend(
            [
                transforms.RandomHorizontalFlip(p=0.5),
                transforms.RandomVerticalFlip(p=0.5),
                transforms.RandomRotation(degrees=180, fill=0),
                transforms.ColorJitter(brightness=0.10, contrast=0.10),
            ]
        )

    ops.extend(
        [
            transforms.ToTensor(),
            transforms.Normalize(mean=list(mean), std=list(std)),
        ]
    )
    return transforms.Compose(ops)
