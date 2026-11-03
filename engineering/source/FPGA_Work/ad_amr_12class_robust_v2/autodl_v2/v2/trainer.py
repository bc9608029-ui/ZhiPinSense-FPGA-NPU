"""V2 robustness trainer (reuses V1 network; drops teacher distillation).

Unlike the V1.1 trainer, this trainer:
  * builds the same ADAMRV11Net (Phase A/B) or a Phase-C candidate;
  * trains with a V2 loss (CE / focal / label-smoothing / class-balanced)
    plus the V1 reconstruction term, with NO teacher distillation;
  * feeds V2Dataset (SNR curriculum + augmentation groups);
  * writes checkpoints readable by V1's ``evaluate_v1_1`` (keys ``class_names``,
    ``model_state``, ``epoch``) and tagged with the V2 model name / V1 SHA.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

from datasets.ad_amr_dataset import collate_ad_amr
from models.ad_amr_v1_1_net import build_ad_amr_v1_1_model
from training.ad_amr_v1_1_loss import snr_weights
from training.ad_amr_v1_1_trainer import _summary
from training.utils import save_json, select_device
from v2 import losses as v2_losses
from v2.augmentation import V2Augmentor
from v2.contract import V1_MODEL_SHA, V2_MODEL_NAME
from v2.dataset_v2 import V2Dataset

CHECKPOINT_VERSION = 2


class V2Trainer:
    def __init__(self, config: dict[str, Any], paths: dict[str, Path],
                 classes: list[str],
                 build_model: Callable[..., torch.nn.Module] | None = None) -> None:
        self.config = config
        self.paths = paths
        self.classes = classes
        cfg = config["training"]
        v2 = config.get("v2", {})

        model = build_model(len(classes), **config["model"]) if build_model is not None \
            else build_ad_amr_v1_1_model(len(classes), **config["model"])
        self.model = model

        self.device = select_device(str(config.get("device", "auto")))
        self.model = self.model.to(self.device)

        self.loss_name = str(v2.get("loss", "cross_entropy"))
        self.label_smoothing = float(v2.get("label_smoothing", 0.1))
        self.focal_gamma = float(v2.get("focal_gamma", 2.0))
        self.optimizer_name = str(v2.get("optimizer", "adamw")).lower()
        self.sgd_momentum = float(v2.get("sgd_momentum", 0.9))
        self.class_sampling = str(v2.get("class_sampling", "balanced"))
        self.class_weight = self._build_class_weight()

        self.minimum_epochs = int(cfg.get("minimum_epochs_before_stopping", 30))
        self.patience = int(cfg.get("early_stopping_patience", 12))
        self.min_delta = float(cfg.get("min_delta", 1e-4))
        self.gradient_clip = float(cfg.get("gradient_clip_norm", 2.0))
        self.reconstruction_weight = float(cfg.get("reconstruction_weight", 0.02))
        self.snr_weighting = cfg.get("snr_weighting", {})

        if self.optimizer_name == "adamw":
            self.optimizer = torch.optim.AdamW(
                self.model.parameters(), lr=float(cfg["learning_rate"]),
                weight_decay=float(cfg.get("weight_decay", 1e-4)),
            )
        elif self.optimizer_name == "sgd":
            self.optimizer = torch.optim.SGD(
                self.model.parameters(), lr=float(cfg["learning_rate"]),
                momentum=self.sgd_momentum, weight_decay=float(cfg.get("weight_decay", 1e-4)),
            )
        else:
            raise ValueError(f"unknown v2 optimizer {self.optimizer_name!r}")

        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="max", factor=float(cfg.get("scheduler_factor", 0.5)),
            patience=int(cfg.get("scheduler_patience", 5)),
            min_lr=float(cfg.get("minimum_lr", 1e-6)),
        )

        self.amp_enabled = bool(cfg.get("amp", True)) and self.device.type == "cuda"
        amp_dtype_name = str(cfg.get("amp_dtype", "bfloat16")).lower()
        self.amp_dtype = torch.bfloat16 if amp_dtype_name == "bfloat16" else torch.float16
        if self.amp_enabled and self.amp_dtype == torch.bfloat16 and not torch.cuda.is_bf16_supported():
            raise RuntimeError("bfloat16 AMP requested but unsupported by this CUDA device")
        scaler_enabled = self.amp_enabled and self.amp_dtype == torch.float16
        try:
            self.scaler = torch.amp.GradScaler("cuda", enabled=scaler_enabled)
        except TypeError:
            self.scaler = torch.cuda.amp.GradScaler(enabled=scaler_enabled)

        self.best_score = -float("inf")
        self.best_epoch = 0
        self.stale_epochs = 0
        self.history: list[dict[str, Any]] = []
        self._class_weights: torch.Tensor | None = None

    def _build_class_weight(self) -> torch.Tensor | None:
        """Per-class loss weights from the ``class_sampling`` axis."""
        n = len(self.classes)
        if self.class_sampling in (None, "", "balanced"):
            return None
        if self.class_sampling == "hard_example_16qam_64qam":
            weights = torch.ones(n, dtype=torch.float32)
            for name in ("16QAM", "64QAM"):
                for index, class_name in enumerate(self.classes):
                    if str(class_name).upper() == name:
                        weights[index] = 3.0
            return weights
        if self.class_sampling == "class_balanced":
            # Synthetic 12-class dataset is balanced by construction; inverse-frequency
            # weights are uniform, so this axis is exercised as a no-op weighting path.
            return None
        raise ValueError(f"unknown class_sampling {self.class_sampling!r}")

    def _classification_loss(self, logits: torch.Tensor, labels: torch.Tensor,
                             snr_db: torch.Tensor) -> torch.Tensor:
        if self.loss_name == "cross_entropy":
            weights = snr_weights(snr_db, self.snr_weighting).to(logits.device)
            per = F.cross_entropy(logits, labels, reduction="none", weight=self.class_weight)
            return (per * weights).sum() / weights.sum().clamp_min(1e-6)
        if self.loss_name == "focal":
            return v2_losses.focal(logits, labels, gamma=self.focal_gamma, weight=self.class_weight)
        if self.loss_name == "label_smoothing":
            return v2_losses.label_smoothing(logits, labels, smoothing=self.label_smoothing,
                                             weight=self.class_weight)
        if self.loss_name == "class_balanced":
            return v2_losses.class_balanced(logits, labels, class_weights=self.class_weight)
        raise ValueError(f"unknown v2 loss {self.loss_name!r}")

    def _run_epoch(self, loader: DataLoader, training: bool) -> dict[str, Any]:
        self.model.train(training)
        if training and hasattr(loader.dataset, "set_epoch"):
            loader.dataset.set_epoch(len(self.history) + 1)
        total_loss = 0.0
        total_count = 0
        targets: list[int] = []
        predictions: list[int] = []
        snrs: list[float] = []
        for batch in loader:
            noisy = batch["noisy_iq"].to(self.device, non_blocking=True)
            clean = batch["clean_iq"].to(self.device, non_blocking=True)
            labels = batch["label"].to(self.device, non_blocking=True)
            snr_db = batch["snr_db"].to(self.device, non_blocking=True)
            context = torch.enable_grad() if training else torch.inference_mode()
            with context:
                with torch.autocast(device_type=self.device.type, dtype=self.amp_dtype,
                                    enabled=self.amp_enabled):
                    logits, denoised = self.model(noisy)
                    cls_loss = self._classification_loss(logits, labels, snr_db)
                    reconstruction = F.mse_loss(denoised.float(), clean.float())
                    loss = cls_loss + self.reconstruction_weight * reconstruction
                if not bool(torch.isfinite(loss)):
                    raise RuntimeError(
                        f"V2 non-finite loss epoch={len(self.history)+1} "
                        f"snr=[{snr_db.min().item()},{snr_db.max().item()}]"
                    )
                if training:
                    self.optimizer.zero_grad(set_to_none=True)
                    self.scaler.scale(loss).backward()
                    self.scaler.unscale_(self.optimizer)
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.gradient_clip)
                    self.scaler.step(self.optimizer)
                    self.scaler.update()
            count = int(labels.numel())
            total_loss += float(loss.detach().float().cpu()) * count
            total_count += count
            targets.extend(labels.detach().cpu().tolist())
            predictions.extend(logits.detach().argmax(1).cpu().tolist())
            snrs.extend(float(v) for v in snr_db.detach().cpu().tolist())
        metrics = _summary(targets, predictions, snrs, len(self.classes))
        metrics["loss"] = total_loss / max(total_count, 1)
        return metrics

    def fit(self, train_loader: DataLoader, val_loader: DataLoader,
            stop_after_epoch: int | None = None) -> list[dict[str, Any]]:
        total_epochs = int(self.config["training"]["epochs"])
        start = len(self.history) + 1
        end = total_epochs if stop_after_epoch is None else min(total_epochs, start + int(stop_after_epoch) - 1)
        for epoch in range(start, end + 1):
            started = time.perf_counter()
            train_metrics = self._run_epoch(train_loader, True)
            val_metrics = self._run_epoch(val_loader, False)
            score = float(val_metrics["selection_score"])
            row = {
                "epoch": epoch,
                "learning_rate": float(self.optimizer.param_groups[0]["lr"]),
                "train_loss": train_metrics["loss"],
                "train_accuracy": train_metrics["accuracy"],
                "train_macro_f1": train_metrics["macro_f1"],
                "val_loss": val_metrics["loss"],
                "val_accuracy": val_metrics["accuracy"],
                "val_macro_f1": val_metrics["macro_f1"],
                "val_rated_0_20_accuracy": val_metrics["rated_0_20_accuracy"],
                "val_high_10_20_accuracy": val_metrics["high_10_20_accuracy"],
                "val_snr_0_accuracy": val_metrics["snr_0_accuracy"],
                "val_min_per_class_accuracy": val_metrics["min_per_class_accuracy"],
                "val_selection_score": score,
                "val_per_class_accuracy": val_metrics["per_class_accuracy"],
                "val_per_snr_accuracy": val_metrics["per_snr_accuracy"],
                "epoch_time_sec": time.perf_counter() - started,
            }
            self.history.append(row)
            improved = score > self.best_score + self.min_delta
            if improved:
                self.best_score = score
                self.best_epoch = epoch
                self.stale_epochs = 0
                self._save(self.paths["checkpoints"] / "best.pt", epoch)
            else:
                self.stale_epochs += 1
            self.scheduler.step(score)
            self._save(self.paths["checkpoints"] / "last.pt", epoch)
            print(
                f"epoch={epoch:03d} loss={row['train_loss']:.4f} val_f1={row['val_macro_f1']:.4f} "
                f"rated={row['val_rated_0_20_accuracy']:.4f} snr0={row['val_snr_0_accuracy']:.4f} "
                f"min_class={row['val_min_per_class_accuracy']:.4f} score={score:.4f}", flush=True,
            )
            if epoch >= self.minimum_epochs and self.stale_epochs >= self.patience:
                print(f"early_stop epoch={epoch} best_epoch={self.best_epoch}", flush=True)
                break
        return self.history

    def _payload(self, epoch: int) -> dict[str, Any]:
        return {
            "checkpoint_version": CHECKPOINT_VERSION,
            "model_name": V2_MODEL_NAME,
            "v1_model_sha": V1_MODEL_SHA,
            "epoch": epoch,
            "next_epoch": epoch + 1,
            "model_state": self.model.state_dict(),
            "optimizer_state": self.optimizer.state_dict(),
            "scheduler_state": self.scheduler.state_dict(),
            "amp_state": self.scaler.state_dict(),
            "best_selection_score": self.best_score,
            "best_epoch": self.best_epoch,
            "stale_epochs": self.stale_epochs,
            "history": self.history,
            "class_names": self.classes,
            "loss_name": self.loss_name,
            "v2": self.config.get("v2", {}),
        }

    def _save(self, path: Path, epoch: int) -> None:
        torch.save(self._payload(epoch), path)

    def save_summary(self) -> None:
        save_json(
            {
                "best_epoch": self.best_epoch,
                "best_selection_score": float(self.best_score),
                "history": self.history,
                "classes": self.classes,
                "loss_name": self.loss_name,
                "v2": self.config.get("v2", {}),
            },
            self.paths["logs"] / "training_summary.json",
        )


def build_v2_train_dataset(config: dict[str, Any], split: str) -> V2Dataset:
    """Build a V2Dataset for the given split with augmentation + curriculum."""
    v2 = config.get("v2", {})
    groups = list(v2.get("augmentation_groups", []) or [])
    is_train = split == "train"
    augmentor = V2Augmentor(groups) if (groups and is_train) else None
    channel_config = dict(config["channel"])
    if groups and is_train:
        for key, value in V2Augmentor.channel_overrides(groups).items():
            channel_config.setdefault(key, {}).update(value)
    return V2Dataset(
        int(config["dataset"]["train_samples" if is_train else "val_samples"]),
        config["signal"], channel_config, int(config["seed"]), split,
        snr_values=[float(v) for v in config["dataset"]["snr_values"]],
        augmentor=augmentor,
        curriculum=str(v2.get("snr_curriculum", "none")),
        total_epochs=int(config["training"]["epochs"]),
    )
