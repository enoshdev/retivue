"""Dataset loader enforcing Phase 8 split isolation, missing-file verification, and official test exclusion."""

import hashlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
from PIL import Image
from torch.utils.data import Dataset

from ai.config import CLASS_INDEX_TO_LABEL


def load_phase8_split_dataframe(
    split_manifest_csv: Path,
    processed_dataset_dir: Path,
    split_filter: Optional[str] = None,
    verify_files_exist: bool = True,
) -> Tuple[pd.DataFrame, str]:
    """
    Load Phase 8 split manifest safely, compute its SHA-256 digest, refuse any official test_images,
    and verify every referenced processed image exists on disk.
    """
    if not split_manifest_csv.is_file():
        raise FileNotFoundError(f"Split manifest not found: '{split_manifest_csv}'.")

    manifest_sha256 = hashlib.sha256(split_manifest_csv.read_bytes()).hexdigest()
    df = pd.read_csv(split_manifest_csv)

    required_cols = {
        "relative_path",
        "processed_relative_path",
        "sha256_checksum",
        "standardized_grade_numeric",
        "split",
    }
    missing_cols = required_cols - set(df.columns)
    if missing_cols:
        raise ValueError(f"Split manifest missing required columns: {sorted(missing_cols)}")

    # Non-negotiable isolation guard: never admit official unlabeled APTOS test_images
    if df["relative_path"].astype(str).str.startswith("test_images/").any():
        raise ValueError("Official APTOS test_images detected inside split manifest; refusing to load.")

    # Verify zero train/val SHA-256 leakage if full manifest loaded
    train_shas = set(df[df["split"] == "train"]["sha256_checksum"].dropna().astype(str))
    val_shas = set(df[df["split"] == "val"]["sha256_checksum"].dropna().astype(str))
    overlap = train_shas & val_shas
    if overlap:
        raise ValueError(f"Train/val SHA-256 leakage detected across {len(overlap)} hashes.")

    if split_filter is not None:
        if split_filter not in ("train", "val"):
            raise ValueError(f"Unsupported split_filter '{split_filter}'; expected 'train' or 'val'.")
        df = df[df["split"] == split_filter].copy()

    df = df.reset_index(drop=True)
    if verify_files_exist:
        missing_files: List[str] = []
        for rel in df["processed_relative_path"].astype(str):
            p = (processed_dataset_dir / rel).resolve()
            if not p.is_file() or p.stat().st_size == 0:
                missing_files.append(rel)
        if missing_files:
            raise FileNotFoundError(
                f"{len(missing_files)} processed image(s) missing/empty (first: '{missing_files[0]}')."
            )

    return df, manifest_sha256


class RetinalSplitDataset(Dataset):
    """PyTorch Dataset backed strictly by Phase 8 processed RGB PNGs and verified split assignments."""

    def __init__(
        self,
        df: pd.DataFrame,
        processed_dataset_dir: Path,
        transform=None,
    ) -> None:
        self.df = df.reset_index(drop=True)
        self.processed_dataset_dir = Path(processed_dataset_dir).resolve()
        self.transform = transform

        self.paths: List[Path] = [
            (self.processed_dataset_dir / str(rel)).resolve()
            for rel in self.df["processed_relative_path"]
        ]
        self.labels: List[int] = [int(g) for g in self.df["standardized_grade_numeric"]]
        for g in self.labels:
            if g not in CLASS_INDEX_TO_LABEL:
                raise ValueError(f"Invalid DR severity label '{g}' encountered.")

    def __len__(self) -> int:
        return len(self.paths)

    def __getitem__(self, idx: int):
        img_path = self.paths[idx]
        label = self.labels[idx]
        with Image.open(img_path) as img:
            rgb = img.convert("RGB")
            if self.transform is not None:
                tensor = self.transform(rgb)
            else:
                from torchvision.transforms import ToTensor

                tensor = ToTensor()(rgb)
        return tensor, label, idx
