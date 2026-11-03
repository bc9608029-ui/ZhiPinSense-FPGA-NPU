"""Robust V1.1 trainer with gate-aware selection and strict resume."""

from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch.utils.data import DataLoader

from models.ad_amr_v1_1_net import ADAMRV11Net
from models.ad_amr_v1_1_teachers import TeacherEnsemble
from training.ad_amr_v1_1_loss import ad_amr_v1_1_loss
from training.metrics import classification_metrics

CHECKPOINT_VERSION = 1


def _summary(targets: list[int], predictions: list[int], snrs: list[float],
             num_classes: int) -> dict[str, Any]:
    metrics = classification_metrics(targets, predictions, num_classes)
    per_class = [float(v) for v in metrics["per_class_accuracy"]]

    def slice_accuracy(predicate: Any) -> float:
        selected = [p == t for p, t, snr in zip(predictions, targets, snrs) if predicate(snr)]
        return float(sum(selected) / len(selected)) if selected else 0.0

    per_snr: dict[str, float] = {}
    for value in sorted(set(snrs)):
        per_snr[f"{value:.0f}"] = slice_accuracy(lambda snr, value=value: snr == value)
    result = {
        "accuracy": float(metrics["accuracy"]),
        "macro_f1": float(metrics["macro_f1"]),
        "per_class_accuracy": per_class,
        "min_per_class_accuracy": min(per_class),
        "rated_0_20_accuracy": slice_accuracy(lambda snr: 0.0 <= snr <= 20.0),
        "high_10_20_accuracy": slice_accuracy(lambda snr: 10.0 <= snr <= 20.0),
        "snr_0_accuracy": slice_accuracy(lambda snr: snr == 0.0),
        "per_snr_accuracy": per_snr,
    }
    result["selection_score"] = (
        0.45 * result["macro_f1"]
        + 0.30 * result["rated_0_20_accuracy"]
        + 0.15 * result["snr_0_accuracy"]
        + 0.10 * result["min_per_class_accuracy"]
    )
    return result


class ADAMRV11Trainer:
    def __init__(self, model: ADAMRV11Net, teachers: TeacherEnsemble | None,
                 device: torch.device, config: dict[str, Any], paths: dict[str, Path],
                 classes: list[str]) -> None:
        self.model = model
        self.teachers = teachers
        self.device = device
        self.config = config
        self.paths = paths
        self.classes = classes
        cfg = config["training"]
        self.minimum_epochs = int(cfg.get("minimum_epochs_before_stopping", 30))
        self.patience = int(cfg.get("early_stopping_patience", 12))
        self.min_delta = float(cfg.get("min_delta", 1e-4))
        self.gradient_clip = float(cfg.get("gradient_clip_norm", 2.0))
        self.amp_enabled = bool(cfg.get("amp", True)) and device.type == "cuda"
        try:
            self.scaler = torch.amp.GradScaler("cuda", enabled=self.amp_enabled)
        except TypeError:
            self.scaler = torch.cuda.amp.GradScaler(enabled=self.amp_enabled)
        self.optimizer = torch.optim.AdamW(
            self.model.parameters(), lr=float(cfg["learning_rate"]),
            weight_decay=float(cfg.get("weight_decay", 1e-4)),
        )
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer, mode="max", factor=float(cfg.get("scheduler_factor", 0.5)),
            patience=int(cfg.get("scheduler_patience", 5)), min_lr=float(cfg.get("minimum_lr", 1e-6)),
        )
        self.best_score = -float("inf")
        self.best_epoch = 0
        self.stale_epochs = 0
        self.history: list[dict[str, Any]] = []

    def _run_epoch(self, loader: DataLoader, training: bool) -> dict[str, Any]:
        self.model.train(training)
        if hasattr(loader.dataset, "set_epoch") and training:
            loader.dataset.set_epoch(len(self.history) + 1)
        total_loss = 0.0
        total_count = 0
        targets: list[int] = []
        predictions: list[int] = []
        snrs: list[float] = []
        for batch_index, batch in enumerate(loader):
            noisy = batch["noisy_iq"].to(self.device, non_blocking=True)
            clean = batch["clean_iq"].to(self.device, non_blocking=True)
            labels = batch["label"].to(self.device, non_blocking=True)
            snr_db = batch["snr_db"].to(self.device, non_blocking=True)
            teacher_logits = None
            if training and self.teachers is not None and self.teachers.enabled:
                teacher_logits = self.teachers.logits(noisy.float())
            context = torch.enable_grad() if training else torch.inference_mode()
            with context:
                with torch.autocast(device_type=self.device.type, dtype=torch.float16,
                                    enabled=self.amp_enabled):
                    logits, denoised = self.model(noisy)
                    loss, components = ad_amr_v1_1_loss(
                        logits, denoised, clean, labels, snr_db,
                        self.config["training"], self.teachers if training else None,
                        teacher_logits,
                    )
                if not bool(torch.isfinite(loss)):
                    details = {name: float(value.detach().float().cpu()) for name, value in components.items()}
                    raise RuntimeError(
                        f"V1.1 non-finite loss epoch={len(self.history)+1} batch={batch_index} "
                        f"snr=[{snr_db.min().item()},{snr_db.max().item()}] components={details}"
                    )
                if training:
                    self.optimizer.zero_grad(set_to_none=True)
                    self.scaler.scale(loss).backward()
                    self.scaler.unscale_(self.optimizer)
                    torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.gradient_clip)
                    for parameter in self.model.parameters():
                        if parameter.grad is not None and not bool(torch.isfinite(parameter.grad).all()):
                            raise RuntimeError(f"V1.1 non-finite gradient at batch {batch_index}")
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
                self._save(self.paths["checkpoints"] / "best.pt", epoch, train_loader)
            else:
                self.stale_epochs += 1
            self.scheduler.step(score)
            self._save(self.paths["checkpoints"] / "last.pt", epoch, train_loader)
            print(
                f"epoch={epoch:03d} loss={row['train_loss']:.4f} val_f1={row['val_macro_f1']:.4f} "
                f"rated={row['val_rated_0_20_accuracy']:.4f} snr0={row['val_snr_0_accuracy']:.4f} "
                f"min_class={row['val_min_per_class_accuracy']:.4f} score={score:.4f}", flush=True,
            )
            if epoch >= self.minimum_epochs and self.stale_epochs >= self.patience:
                print(f"early_stop epoch={epoch} best_epoch={self.best_epoch}", flush=True)
                break
        return self.history

    def _payload(self, epoch: int, train_loader: DataLoader) -> dict[str, Any]:
        generator = train_loader.generator
        if generator is None:
            raise RuntimeError("strict resume requires a dedicated train DataLoader generator")
        cuda_rng = [v.detach().cpu() for v in torch.cuda.get_rng_state_all()] if torch.cuda.is_available() else []
        return {
            "checkpoint_version": CHECKPOINT_VERSION,
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
            "train_loader_generator_state": generator.get_state().detach().cpu(),
            "rng_state": {
                "python": random.getstate(), "numpy": np.random.get_state(),
                "torch_cpu": torch.get_rng_state().detach().cpu(), "torch_cuda": cuda_rng,
            },
        }

    def _save(self, path: Path, epoch: int, train_loader: DataLoader) -> None:
        torch.save(self._payload(epoch, train_loader), path)

    def load_resume(self, path: Path, train_loader: DataLoader) -> int:
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
        if int(checkpoint.get("checkpoint_version", -1)) != CHECKPOINT_VERSION:
            raise RuntimeError("unsupported V1.1 checkpoint version")
        if list(checkpoint.get("class_names", [])) != self.classes:
            raise RuntimeError("checkpoint class contract differs from requested V1.1 class contract")
        self.model.load_state_dict(checkpoint["model_state"], strict=True)
        self.optimizer.load_state_dict(checkpoint["optimizer_state"])
        self.scheduler.load_state_dict(checkpoint["scheduler_state"])
        self.scaler.load_state_dict(checkpoint.get("amp_state", {}))
        for state in self.optimizer.state.values():
            for key, value in list(state.items()):
                if isinstance(value, torch.Tensor):
                    state[key] = value.to(self.device)
        self.best_score = float(checkpoint["best_selection_score"])
        self.best_epoch = int(checkpoint["best_epoch"])
        self.stale_epochs = int(checkpoint["stale_epochs"])
        self.history = list(checkpoint["history"])
        loader_state = checkpoint["train_loader_generator_state"]
        if not isinstance(loader_state, torch.Tensor) or loader_state.dtype != torch.uint8:
            raise RuntimeError("invalid DataLoader RNG state")
        if train_loader.generator is None:
            raise RuntimeError("strict resume requires a dedicated train DataLoader generator")
        train_loader.generator.set_state(loader_state.detach().cpu())
        rng = checkpoint["rng_state"]
        random.setstate(rng["python"])
        np.random.set_state(rng["numpy"])
        torch.set_rng_state(rng["torch_cpu"].detach().cpu())
        if self.device.type == "cuda" and rng.get("torch_cuda"):
            states = rng["torch_cuda"]
            if len(states) != torch.cuda.device_count():
                raise RuntimeError("CUDA RNG device-count mismatch during resume")
            torch.cuda.set_rng_state_all([state.detach().cpu() for state in states])
        return int(checkpoint["epoch"])
