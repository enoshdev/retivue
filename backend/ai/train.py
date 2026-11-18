"""Baseline DR classifier training CLI orchestrator (2-stage transfer, imbalance strategies, resume & logs)."""

import argparse
import csv
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, WeightedRandomSampler

from ai.checkpoint import (
    collect_environment_metadata,
    save_checkpoint_with_provenance,
    verify_and_load_checkpoint,
)
from ai.config import (
    CLASS_INDEX_TO_LABEL,
    TrainingConfig,
    get_safe_model_root,
    resolve_torch_device,
    seed_everything,
)
from ai.dataset import RetinalSplitDataset, load_phase8_split_dataframe
from ai.evaluate import evaluate_checkpoint_on_split
from ai.metrics import compute_dr_evaluation_metrics
from ai.models import build_classifier_model, count_parameters, set_backbone_trainable
from ai.transforms import build_retinal_transforms
from data_pipeline.directory_manager import DatasetDirectoryManager


def compute_train_loss_weights(train_labels: List[int], strategy: str, num_classes: int = 5) -> Optional[torch.Tensor]:
    """Compute per-class CrossEntropyLoss weights strictly from training labels without touching val."""
    counts = np.bincount(np.asarray(train_labels, dtype=np.int64), minlength=num_classes).astype(np.float64)
    if strategy == "unweighted" or strategy == "weighted_sampler":
        return None

    max_cnt = max(1.0, float(counts.max()))
    if strategy == "weighted_loss_sqrt_inv":
        weights = np.array(
            [(max_cnt / c) ** 0.5 if c > 0 else 0.0 for c in counts],
            dtype=np.float32,
        )
        return torch.tensor(weights, dtype=torch.float32)

    if strategy == "weighted_loss_effective":
        beta = 0.999
        raw = np.array(
            [(1.0 - beta) / (1.0 - (beta**c)) if c > 0 else 0.0 for c in counts],
            dtype=np.float64,
        )
        pos = raw[raw > 0]
        if len(pos) > 0:
            raw = raw / pos.mean()
        return torch.tensor(raw.astype(np.float32), dtype=torch.float32)

    raise ValueError(f"Unsupported imbalance_strategy '{strategy}'.")


def _build_weighted_sampler(train_labels: List[int], num_classes: int = 5, seed: int = 42) -> WeightedRandomSampler:
    counts = np.bincount(np.asarray(train_labels, dtype=np.int64), minlength=num_classes).astype(np.float64)
    class_w = np.array([1.0 / c if c > 0 else 0.0 for c in counts], dtype=np.float64)
    sample_w = torch.tensor([class_w[y] for y in train_labels], dtype=torch.double)
    gen = torch.Generator()
    gen.manual_seed(seed)
    return WeightedRandomSampler(weights=sample_w, num_samples=len(train_labels), replacement=True, generator=gen)


def _evaluate_val_epoch(
    model: nn.Module,
    val_loader: DataLoader,
    criterion: nn.Module,
    device: torch.device,
) -> Dict[str, Any]:
    model.eval()
    losses: List[float] = []
    probs_list: List[np.ndarray] = []
    labels_list: List[np.ndarray] = []
    mem_fmt = torch.channels_last if device.type == "cpu" else torch.contiguous_format

    with torch.inference_mode():
        for x_b, y_b, _ in val_loader:
            x_b = x_b.to(device, memory_format=mem_fmt)
            y_b = y_b.to(device)
            logits = model(x_b)
            loss = criterion(logits, y_b)
            losses.append(float(loss.detach().cpu().item()))
            probs_list.append(torch.softmax(logits, dim=1).detach().cpu().numpy())
            labels_list.append(y_b.detach().cpu().numpy())

    y_probs = np.concatenate(probs_list, axis=0)
    y_true = np.concatenate(labels_list, axis=0)
    metrics = compute_dr_evaluation_metrics(y_true, y_probs)
    metrics["val_loss"] = round(float(np.mean(losses)), 6) if losses else 0.0
    return metrics


def run_training_experiment(
    config: TrainingConfig,
    split_manifest_csv: Path,
    processed_dataset_dir: Path,
    model_root: Optional[Path] = None,
    run_id: Optional[str] = None,
    resume_checkpoint: Optional[Path] = None,
    run_post_eval: bool = True,
) -> Dict[str, Any]:
    """
    Train baseline DR classifier deterministically with Stage-1 head warmup, Stage-2 fine-tuning,
    early stopping on val Macro F1, atomic checkpoints, and full provenance manifests.
    """
    seed_everything(config.seed, deterministic=config.deterministic_mode)
    dev_info = resolve_torch_device(config.device_preference)
    device = torch.device(dev_info["device"])

    resolved_model_root = model_root or get_safe_model_root()
    resolved_run_id = run_id or f"{config.experiment_name}_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
    exp_dir = (resolved_model_root / "experiments" / resolved_run_id).resolve()
    exp_dir.mkdir(parents=True, exist_ok=True)

    train_df, manifest_sha = load_phase8_split_dataframe(
        split_manifest_csv=split_manifest_csv,
        processed_dataset_dir=processed_dataset_dir,
        split_filter="train",
        verify_files_exist=True,
    )
    val_df, _ = load_phase8_split_dataframe(
        split_manifest_csv=split_manifest_csv,
        processed_dataset_dir=processed_dataset_dir,
        split_filter="val",
        verify_files_exist=True,
    )

    norm_mean, norm_std = config.get_normalization_stats()
    train_tf = build_retinal_transforms(
        input_size=config.input_size,
        mean=norm_mean,
        std=norm_std,
        is_train=True,
        augmentation_enabled=config.augmentation_enabled,
    )
    val_tf = build_retinal_transforms(
        input_size=config.input_size,
        mean=norm_mean,
        std=norm_std,
        is_train=False,
        augmentation_enabled=False,
    )

    train_ds = RetinalSplitDataset(train_df, processed_dataset_dir, transform=train_tf)
    val_ds = RetinalSplitDataset(val_df, processed_dataset_dir, transform=val_tf)

    if config.imbalance_strategy == "weighted_sampler":
        sampler = _build_weighted_sampler(train_ds.labels, num_classes=config.num_classes, seed=config.seed)
        train_loader = DataLoader(
            train_ds,
            batch_size=config.batch_size,
            sampler=sampler,
            num_workers=config.num_workers,
        )
    else:
        gen = torch.Generator()
        gen.manual_seed(config.seed)
        train_loader = DataLoader(
            train_ds,
            batch_size=config.batch_size,
            shuffle=True,
            generator=gen,
            num_workers=config.num_workers,
        )

    val_loader = DataLoader(
        val_ds,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=config.num_workers,
    )

    mem_fmt = torch.channels_last if device.type == "cpu" else torch.contiguous_format
    model = build_classifier_model(
        architecture=config.architecture,
        num_classes=config.num_classes,
        pretrained=config.pretrained,
        dropout_p=config.dropout_p,
    ).to(device, memory_format=mem_fmt)

    loss_weights = compute_train_loss_weights(
        train_ds.labels, strategy=config.imbalance_strategy, num_classes=config.num_classes
    )
    if loss_weights is not None:
        loss_weights = loss_weights.to(device)
    criterion = nn.CrossEntropyLoss(weight=loss_weights)

    run_manifest = {
        "run_id": resolved_run_id,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "split_manifest_csv": str(split_manifest_csv),
        "split_manifest_sha256": manifest_sha,
        "processed_dataset_dir": str(processed_dataset_dir),
        "train_count": len(train_ds),
        "val_count": len(val_ds),
        "patient_level_split_verified": False,
        "training_config": config.to_dict(),
        "computed_class_weights": loss_weights.detach().cpu().tolist() if loss_weights is not None else None,
        "device_resolved": dev_info,
        "environment": collect_environment_metadata(),
    }
    with open(exp_dir / "run_manifest.json", "w", encoding="utf-8") as rmf:
        json.dump(run_manifest, rmf, indent=2)

    history_jsonl = exp_dir / "epoch_history.jsonl"
    history_csv = exp_dir / "epoch_history.csv"
    best_ckpt_path = exp_dir / "best_checkpoint.pt"
    last_ckpt_path = exp_dir / "last_checkpoint.pt"

    start_epoch = 1
    best_macro_f1 = -1.0
    best_qwk = -1.0
    epochs_without_improve = 0
    history_rows: List[Dict[str, Any]] = []

    resumed_payload: Optional[Dict[str, Any]] = None
    best_meta_path = exp_dir / "best_checkpoint_meta.json"
    best_meta: Optional[Dict[str, Any]] = None
    if best_meta_path.is_file():
        best_meta = json.loads(best_meta_path.read_text(encoding="utf-8"))

    if resume_checkpoint and resume_checkpoint.is_file():
        resumed = verify_and_load_checkpoint(resume_checkpoint, map_location="cpu")
        resumed_payload = resumed
        model.load_state_dict(resumed["model_state_dict"])
        model.to(device, memory_format=mem_fmt)
        start_epoch = int(resumed.get("epoch", 0)) + 1
        best_macro_f1 = float(resumed.get("best_metric_value", -1.0))
        if history_jsonl.is_file():
            for line in history_jsonl.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    history_rows.append(json.loads(line))
        if history_rows:
            best_rows = [r for r in history_rows if r.get("is_best")]
            if best_rows:
                best_qwk = float(best_rows[-1].get("val_qwk", -1.0))
            for r in reversed(history_rows):
                if r.get("is_best"):
                    break
                epochs_without_improve += 1

    current_stage: Optional[str] = None
    optimizer: Optional[torch.optim.Optimizer] = None
    scheduler: Optional[Any] = None

    def _configure_stage(stage_name: str, epoch_idx: int) -> None:
        nonlocal current_stage, optimizer, scheduler
        if stage_name == current_stage and optimizer is not None:
            return
        current_stage = stage_name
        if stage_name == "warmup":
            set_backbone_trainable(model, config.architecture, trainable=False)
            lr = config.warmup_lr
            optimizer = torch.optim.AdamW(
                [p for p in model.parameters() if p.requires_grad],
                lr=lr,
                weight_decay=config.weight_decay,
            )
            scheduler = None
        else:
            set_backbone_trainable(
                model,
                config.architecture,
                trainable=True,
                unfreeze_from_block=config.unfreeze_from_block,
            )
            remaining_epochs = max(1, config.max_epochs - max(0, config.warmup_epochs))
            optimizer = torch.optim.AdamW(
                [p for p in model.parameters() if p.requires_grad],
                lr=config.finetune_lr,
                weight_decay=config.weight_decay,
            )
            has_resumed_sch = bool(resumed_payload and resumed_payload.get("stage") == stage_name and resumed_payload.get("scheduler_state_dict"))
            steps_done = max(0, epoch_idx - 1 - config.warmup_epochs)
            if not has_resumed_sch and steps_done > 0:
                for pg in optimizer.param_groups:
                    pg.setdefault("initial_lr", config.finetune_lr)
            scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
                optimizer,
                T_max=remaining_epochs,
                eta_min=1e-6,
                last_epoch=-1 if has_resumed_sch else steps_done - 1 if steps_done > 0 else -1,
            )

        if resumed_payload and resumed_payload.get("stage") == stage_name:
            opt_sd = resumed_payload.get("optimizer_state_dict")
            if opt_sd:
                try:
                    optimizer.load_state_dict(opt_sd)
                except Exception:
                    pass
            sch_sd = resumed_payload.get("scheduler_state_dict")
            if scheduler is not None and sch_sd:
                try:
                    scheduler.load_state_dict(sch_sd)
                except Exception:
                    pass

    for epoch in range(start_epoch, config.max_epochs + 1):
        t0 = time.perf_counter()
        stage = "warmup" if epoch <= config.warmup_epochs else "finetune"
        _configure_stage(stage, epoch)
        assert optimizer is not None

        total_params, trainable_params = count_parameters(model)
        model.train()
        optimizer.zero_grad(set_to_none=True)
        train_losses: List[float] = []

        for step_idx, (x_b, y_b, _) in enumerate(train_loader):
            x_b = x_b.to(device, memory_format=mem_fmt)
            y_b = y_b.to(device)

            logits = model(x_b)
            raw_loss = criterion(logits, y_b)
            scaled_loss = raw_loss / float(max(1, config.grad_accum_steps))
            scaled_loss.backward()
            train_losses.append(float(raw_loss.detach().cpu().item()))

            is_accum_boundary = ((step_idx + 1) % max(1, config.grad_accum_steps) == 0) or (
                (step_idx + 1) == len(train_loader)
            )
            if is_accum_boundary:
                if config.grad_clip_norm > 0:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), config.grad_clip_norm)
                optimizer.step()
                optimizer.zero_grad(set_to_none=True)

        if scheduler is not None:
            scheduler.step()

        cur_lr = float(optimizer.param_groups[0]["lr"])
        val_metrics = _evaluate_val_epoch(model, val_loader, criterion, device)
        elapsed_sec = round(time.perf_counter() - t0, 2)

        val_f1 = float(val_metrics["macro_f1"])
        val_qwk = float(val_metrics["quadratic_weighted_kappa"])
        improved = (val_f1 > best_macro_f1) or (abs(val_f1 - best_macro_f1) < 1e-6 and val_qwk > best_qwk)

        if improved:
            best_macro_f1 = val_f1
            best_qwk = val_qwk
            epochs_without_improve = 0
            best_meta = save_checkpoint_with_provenance(
                checkpoint_path=best_ckpt_path,
                model_state_dict=model.state_dict(),
                optimizer_state_dict=optimizer.state_dict(),
                scheduler_state_dict=scheduler.state_dict() if scheduler else None,
                epoch=epoch,
                stage=stage,
                best_metric_name="val_macro_f1",
                best_metric_value=best_macro_f1,
                config=config,
                split_manifest_sha256=manifest_sha,
                val_metrics_snapshot=val_metrics,
            )
        else:
            epochs_without_improve += 1

        save_checkpoint_with_provenance(
            checkpoint_path=last_ckpt_path,
            model_state_dict=model.state_dict(),
            optimizer_state_dict=optimizer.state_dict(),
            scheduler_state_dict=scheduler.state_dict() if scheduler else None,
            epoch=epoch,
            stage=stage,
            best_metric_name="val_macro_f1",
            best_metric_value=best_macro_f1,
            config=config,
            split_manifest_sha256=manifest_sha,
            val_metrics_snapshot=val_metrics,
        )

        epoch_row = {
            "epoch": epoch,
            "stage": stage,
            "lr": round(cur_lr, 8),
            "trainable_params": trainable_params,
            "total_params": total_params,
            "train_loss": round(float(np.mean(train_losses)), 6) if train_losses else 0.0,
            "val_loss": val_metrics["val_loss"],
            "val_accuracy": val_metrics["overall_accuracy"],
            "val_macro_f1": val_metrics["macro_f1"],
            "val_macro_recall": val_metrics["macro_recall"],
            "val_qwk": val_metrics["quadratic_weighted_kappa"],
            "val_severe_npdr_recall": val_metrics["clinical_safety_slices"]["severe_npdr_grade_3"].get("recall_sensitivity", 0.0),
            "val_pdr_recall": val_metrics["clinical_safety_slices"]["pdr_grade_4"].get("recall_sensitivity", 0.0),
            "val_referable_sensitivity": val_metrics["clinical_safety_slices"]["referable_dr_grades_2_to_4"]["sensitivity_recall"],
            "is_best": improved,
            "elapsed_seconds": elapsed_sec,
        }
        history_rows.append(epoch_row)

        with open(history_jsonl, "w", encoding="utf-8") as hj:
            for r in history_rows:
                hj.write(json.dumps(r) + "\n")
        with open(history_csv, "w", newline="", encoding="utf-8") as hc:
            w = csv.DictWriter(hc, fieldnames=list(epoch_row.keys()))
            w.writeheader()
            for r in history_rows:
                w.writerow(r)

        print(
            f"[Epoch {epoch}/{config.max_epochs} ({stage})] "
            f"train_loss={epoch_row['train_loss']:.4f} val_loss={epoch_row['val_loss']:.4f} "
            f"macro_f1={epoch_row['val_macro_f1']:.4f} qwk={epoch_row['val_qwk']:.4f} "
            f"sev_rec={epoch_row['val_severe_npdr_recall']:.3f} pdr_rec={epoch_row['val_pdr_recall']:.3f} "
            f"best={improved} time={elapsed_sec:.1f}s",
            flush=True,
        )

        # Only trigger early stopping after completing warmup stage
        if stage == "finetune" and epochs_without_improve >= config.early_stopping_patience:
            print(f"Early stopping triggered at epoch {epoch} (patience={config.early_stopping_patience}).", flush=True)
            break

    eval_report = None
    if run_post_eval and best_ckpt_path.is_file():
        eval_report = evaluate_checkpoint_on_split(
            checkpoint_path=best_ckpt_path,
            split_manifest_csv=split_manifest_csv,
            processed_dataset_dir=processed_dataset_dir,
            output_dir=exp_dir,
            split_name="val",
            batch_size=config.batch_size,
            num_workers=config.num_workers,
            device_preference=dev_info["device"],
        )

    return {
        "run_id": resolved_run_id,
        "experiment_dir": str(exp_dir),
        "best_checkpoint_path": str(best_ckpt_path),
        "best_checkpoint_sha256": best_meta["checkpoint_sha256"] if best_meta else None,
        "best_macro_f1": best_macro_f1,
        "best_qwk": best_qwk,
        "epochs_completed": len(history_rows),
        "history_csv": str(history_csv),
        "evaluation_artifacts": eval_report["artifacts"] if eval_report else None,
        "final_val_metrics": eval_report["metrics"] if eval_report else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="RETIVUE Phase 9 Baseline DR Classifier Trainer")
    parser.add_argument("--experiment-name", default="aptos_effnet_b0_baseline")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--architecture", default="efficientnet_b0", choices=["efficientnet_b0", "resnet50"])
    parser.add_argument("--imbalance", default="unweighted", choices=["unweighted", "weighted_loss_effective", "weighted_loss_sqrt_inv", "weighted_sampler"])
    parser.add_argument("--norm-mode", default="imagenet", choices=["imagenet", "aptos_train"])
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--grad-accum", type=int, default=2)
    parser.add_argument("--warmup-epochs", type=int, default=3)
    parser.add_argument("--max-epochs", type=int, default=15)
    parser.add_argument("--patience", type=int, default=5)
    parser.add_argument("--unfreeze-from-block", type=int, default=None)
    parser.add_argument("--device", default="auto", choices=["auto", "xpu", "cuda", "cpu"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-pretrained", action="store_true")
    parser.add_argument("--no-aug", action="store_true")
    parser.add_argument("--resume", default=None, help="Optional path to last_checkpoint.pt")
    args = parser.parse_args()

    cfg = TrainingConfig(
        experiment_name=args.experiment_name,
        architecture=args.architecture,
        pretrained=not args.no_pretrained,
        seed=args.seed,
        device_preference=args.device,
        batch_size=args.batch_size,
        grad_accum_steps=args.grad_accum,
        warmup_epochs=args.warmup_epochs,
        max_epochs=args.max_epochs,
        early_stopping_patience=args.patience,
        unfreeze_from_block=args.unfreeze_from_block,
        imbalance_strategy=args.imbalance,
        normalization_mode=args.norm_mode,
        augmentation_enabled=not args.no_aug,
    )
    dirs = DatasetDirectoryManager().ensure_structure()
    res = run_training_experiment(
        config=cfg,
        split_manifest_csv=dirs.reports / "phase_8_split_manifest.csv",
        processed_dataset_dir=dirs.processed / "aptos",
        run_id=args.run_id,
        resume_checkpoint=Path(args.resume) if args.resume else None,
    )
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
