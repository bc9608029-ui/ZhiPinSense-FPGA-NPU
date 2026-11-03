"""AD-AMR trainer: Adam + ReduceLROnPlateau + AMP + early stopping + full resume.

Numerical policy (mirrors the V3.3 Phase-5 lesson): the forward runs under FP16
autocast when AMP is enabled, but the combined loss is *accumulated in FP32* via an
explicit ``.float()`` so the denoising MSE on deep-negative-SNR IQ can never
overflow FP16.  A non-finite loss is never swallowed: it raises ``RuntimeError``
with full diagnostics.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn.functional as functional
from torch.utils.data import DataLoader

from models.ad_amr_net import ADAMRNet
from training.ad_amr_loss import ad_amr_loss
from training.metrics import classification_metrics

CHECKPOINT_VERSION = 2


def _describe_non_finite(variant: str, epoch: int, batch: int, components: dict[str, torch.Tensor],
                         logits: torch.Tensor, denoised: torch.Tensor) -> str:
    def finite(t: torch.Tensor) -> str:
        return "finite" if bool(torch.isfinite(t).all()) else "NON-FINITE"

    return (
        f"AD-AMR training produced a non-finite loss (variant={variant}, epoch={epoch}, batch={batch}); "
        f"ce={components.get('ce')} {finite(components.get('ce', torch.tensor(0.0)))}, "
        f"mse={components.get('mse')} {finite(components.get('mse', torch.tensor(0.0)))}, "
        f"logits_max_abs={logits.abs().max().item() if logits.numel() else float('nan')}, "
        f"denoised_max_abs={denoised.abs().max().item() if denoised.numel() else float('nan')}"
    )


class ADAMRTrainer:
    def __init__(self, model: ADAMRNet, device: torch.device, config: dict[str, Any],
                 paths: dict[str, Path], classes: list[str], loss_variant: str | None = None) -> None:
        self.model = model
        self.device = device
        self.config = config
        self.paths = paths
        self.classes = classes
        self.num_classes = len(classes)
        training = config["training"]
        self.loss_variant = loss_variant or training["loss"]["variant"]
        self.alpha = float(training["loss"]["alpha"])
        self.gradient_clip_norm = float(training.get("gradient_clip_norm", 1.0))
        self.minimum_epochs = int(training.get("minimum_epochs_before_stopping", 20))
        self.patience = int(training.get("early_stopping_patience", 10))
        self.min_delta = float(training.get("min_delta", 0.0001))
        self.checkpoint_metric = training.get("checkpoint_metric", "val_macro_f1")
        self.checkpoint_mode = training.get("checkpoint_mode", "max")

        self.amp_enabled = bool(training.get("amp", True)) and device.type == "cuda"
        try:
            self.scaler = torch.amp.GradScaler("cuda", enabled=self.amp_enabled)
        except TypeError:
            self.scaler = torch.cuda.amp.GradScaler(enabled=self.amp_enabled)

        self.optimizer = torch.optim.Adam(
            model.parameters(),
            lr=float(training["learning_rate"]),
            weight_decay=float(training.get("weight_decay", 0.0)),
        )
        self.scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer,
            mode="max",
            factor=float(training.get("scheduler_factor", 0.5)),
            patience=int(training.get("scheduler_patience", 5)),
        )

        self.best_metric = -float("inf")
        self.best_epoch = 0
        self.stale_epochs = 0
        self.history: list[dict[str, Any]] = []

    # ------------------------------------------------------------------ fit
    def fit(self, train_loader: DataLoader, val_loader: DataLoader,
            stop_after_epoch: int | None = None) -> list[dict[str, Any]]:
        start_epoch = len(self.history) + 1
        total_epochs = int(self.config["training"]["epochs"])
        if stop_after_epoch is not None:
            total_epochs = start_epoch - 1 + int(stop_after_epoch)

        import time

        for epoch in range(start_epoch, total_epochs + 1):
            if hasattr(train_loader.dataset, "set_epoch"):
                train_loader.dataset.set_epoch(epoch - 1)

            epoch_start = time.perf_counter()
            train_loss = self._train_one_epoch(train_loader, epoch)
            val_loss, val_metrics = self._evaluate(val_loader)
            val_macro_f1 = float(val_metrics["macro_f1"])
            epoch_time = time.perf_counter() - epoch_start
            peak_mem = None
            if self.device.type == "cuda":
                peak_mem = torch.cuda.max_memory_allocated(self.device) / (1024 ** 2)

            learning_rate = self.optimizer.param_groups[0]["lr"]
            self.history.append({
                "epoch": epoch,
                "learning_rate": learning_rate,
                "train_loss": train_loss,
                "val_loss": val_loss,
                "val_accuracy": val_metrics["accuracy"],
                "val_macro_f1": val_macro_f1,
                "epoch_time_sec": epoch_time,
                "peak_mem_mb": peak_mem,
            })

            self.scheduler.step(val_macro_f1)

            improved = val_macro_f1 > self.best_metric + self.min_delta
            if improved:
                self.best_metric = val_macro_f1
                self.best_epoch = epoch
                self.stale_epochs = 0
                self._save_checkpoint(self.paths["checkpoints"] / "best.pt", epoch)
            else:
                self.stale_epochs += 1

            self._save_checkpoint(self.paths["checkpoints"] / "last.pt", epoch, is_last=True)

            if epoch >= self.minimum_epochs and self.stale_epochs >= self.patience:
                break

        return self.history

    def _train_one_epoch(self, loader: DataLoader, epoch: int) -> float:
        self.model.train()
        total = 0.0
        count = 0
        for batch_idx, batch in enumerate(loader):
            clean = batch["clean_iq"].to(self.device)
            noisy = batch["noisy_iq"].to(self.device)
            labels = batch["label"].to(self.device)

            self.optimizer.zero_grad(set_to_none=True)
            with torch.autocast(device_type=self.device.type, dtype=torch.float16, enabled=self.amp_enabled):
                logits, denoised = self.model(noisy)
                loss, components = ad_amr_loss(
                    logits.float(), denoised.float(), labels,
                    clean.float(), noisy.float(), self.loss_variant, self.alpha,
                )
                if not torch.isfinite(loss):
                    raise RuntimeError(_describe_non_finite(self.loss_variant, epoch, batch_idx,
                                                            components, logits, denoised))

            self.scaler.scale(loss).backward()
            self.scaler.unscale_(self.optimizer)
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.gradient_clip_norm)
            self.scaler.step(self.optimizer)
            self.scaler.update()

            total += float(loss.detach().item())
            count += 1
        return total / max(count, 1)

    def _evaluate(self, loader: DataLoader) -> tuple[float, dict[str, Any]]:
        self.model.eval()
        all_preds: list[int] = []
        all_targets: list[int] = []
        total_loss = 0.0
        count = 0
        with torch.inference_mode():
            for batch in loader:
                clean = batch["clean_iq"].to(self.device)
                noisy = batch["noisy_iq"].to(self.device)
                labels = batch["label"].to(self.device)
                with torch.autocast(device_type=self.device.type, dtype=torch.float16, enabled=self.amp_enabled):
                    logits, denoised = self.model(noisy)
                    loss, _ = ad_amr_loss(
                        logits.float(), denoised.float(), labels,
                        clean.float(), noisy.float(), self.loss_variant, self.alpha,
                    )
                total_loss += float(loss.detach().item())
                count += 1
                all_preds.extend(logits.argmax(dim=1).cpu().tolist())
                all_targets.extend(labels.cpu().tolist())
        metrics = classification_metrics(all_targets, all_preds, self.num_classes)
        return total_loss / max(count, 1), metrics

    # ------------------------------------------------------------ checkpoints
    def _checkpoint_payload(self, epoch: int) -> dict[str, Any]:
        cuda_states = torch.cuda.get_rng_state_all() if self.device.type == "cuda" else []
        return {
            "checkpoint_version": CHECKPOINT_VERSION,
            "epoch": epoch,
            "next_epoch": epoch + 1,
            "model_state": self.model.state_dict(),
            "optimizer_state": self.optimizer.state_dict(),
            "scheduler_state": self.scheduler.state_dict(),
            "amp_state": self.scaler.state_dict(),
            "metrics": self.history[-1] if self.history else {},
            "best_validation_metric": self.best_metric,
            "best_epoch": self.best_epoch,
            "early_stopping_state": {"stale_epochs": self.stale_epochs, "patience": self.patience,
                                     "min_delta": self.min_delta},
            "rng_state": {
                "python": random.getstate(),
                "numpy": np.random.get_state(),
                "torch_cpu": torch.get_rng_state(),
                "torch_cuda": cuda_states,
            },
            "history": self.history,
            "class_names": self.classes,
            "loss_variant": self.loss_variant,
        }

    def _save_checkpoint(self, path: Path, epoch: int, is_last: bool = False) -> None:
        payload = self._checkpoint_payload(epoch)
        if is_last:
            payload["dataset_state"] = {"next_epoch": epoch + 1}
        torch.save(payload, path)

    def load_resume(self, path: Path, train_loader: DataLoader | None = None) -> int:
        checkpoint = torch.load(path, map_location="cpu", weights_only=False)
        if checkpoint.get("checkpoint_version") != CHECKPOINT_VERSION:
            raise RuntimeError(f"unsupported checkpoint version {checkpoint.get('checkpoint_version')}")
        if checkpoint.get("loss_variant") not in (None, self.loss_variant):
            raise RuntimeError(
                f"resume loss_variant {checkpoint.get('loss_variant')} != requested {self.loss_variant}"
            )

        self.model.load_state_dict(checkpoint["model_state"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state"])
        if checkpoint.get("scheduler_state"):
            self.scheduler.load_state_dict(checkpoint["scheduler_state"])
        if checkpoint.get("amp_state"):
            self.scaler.load_state_dict(checkpoint["amp_state"])
        self.best_metric = float(checkpoint.get("best_validation_metric", -float("inf")))
        self.best_epoch = int(checkpoint.get("best_epoch", 0))
        self.stale_epochs = int(checkpoint.get("early_stopping_state", {}).get("stale_epochs", 0))
        self.history = list(checkpoint.get("history", []))

        rng = checkpoint.get("rng_state", {})
        random.setstate(rng["python"])
        np.random.set_state(rng["numpy"])
        torch.set_rng_state(rng["torch_cpu"].cpu())
        if self.device.type == "cuda" and rng.get("torch_cuda"):
            states = rng["torch_cuda"]
            states = [s.cpu() if isinstance(s, torch.Tensor) else s for s in states]
            torch.cuda.set_rng_state_all(states)

        # Migrate optimizer tensors to the exact device.
        for state in self.optimizer.state.values():
            for key, value in list(state.items()):
                if isinstance(value, torch.Tensor):
                    state[key] = value.to(self.device)

        return int(checkpoint["epoch"])
