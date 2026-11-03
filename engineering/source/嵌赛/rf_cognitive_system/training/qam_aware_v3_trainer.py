"""AMP-capable, strictly resumable trainer for QAM-Aware V3."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
from torch import nn
from torch.utils.data import DataLoader

from training.metrics import classification_metrics
from training.resumable_trainer import ResumableTrainer


class QAMAwareV3Trainer(ResumableTrainer):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        training = self.config["training"]
        configured_weights = training.get("class_weights")
        class_weights = None
        if configured_weights is not None:
            if isinstance(configured_weights, dict):
                unknown = set(configured_weights) - set(self.class_names)
                if unknown:
                    raise ValueError(f"Unknown class_weights entries: {sorted(unknown)}")
                values = [float(configured_weights.get(name, 1.0)) for name in self.class_names]
            else:
                values = [float(value) for value in configured_weights]
                if len(values) != len(self.class_names):
                    raise ValueError("class_weights length must equal the class count")
            class_weights = torch.tensor(values, dtype=torch.float32, device=self.device)
        self.criterion = nn.CrossEntropyLoss(
            weight=class_weights,
            label_smoothing=float(training.get("label_smoothing", 0.0)),
        )
        self.gradient_clip_norm = float(training.get("gradient_clip_norm", 0.0))
        self.amp_enabled = bool(training.get("amp", True)) and self.device.type == "cuda"
        try:
            self.scaler = torch.amp.GradScaler("cuda", enabled=self.amp_enabled)
        except (AttributeError, TypeError):  # PyTorch 2.0 compatibility.
            self.scaler = torch.cuda.amp.GradScaler(enabled=self.amp_enabled)

    def _run_epoch(self, loader: DataLoader, training: bool) -> dict[str, float]:
        self.model.train(training)
        total_loss = 0.0
        targets: list[int] = []
        predictions: list[int] = []

        for batch in loader:
            inputs, labels = batch[:2]
            inputs = inputs.to(self.device, non_blocking=True)
            labels = labels.to(self.device, non_blocking=True)
            if training:
                self.optimizer.zero_grad(set_to_none=True)

            with torch.set_grad_enabled(training):
                with torch.autocast(
                    device_type=self.device.type,
                    dtype=torch.float16,
                    enabled=self.amp_enabled,
                ):
                    logits = self.model(inputs)
                    loss = self.criterion(logits, labels)
                if not torch.isfinite(loss):
                    raise RuntimeError("V3 training produced a non-finite loss")
                if training:
                    self.scaler.scale(loss).backward()
                    if self.gradient_clip_norm > 0.0:
                        self.scaler.unscale_(self.optimizer)
                        torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.gradient_clip_norm)
                    self.scaler.step(self.optimizer)
                    self.scaler.update()

            self._update_peak_memory()
            total_loss += float(loss.detach().item()) * inputs.shape[0]
            targets.extend(labels.detach().cpu().tolist())
            predictions.extend(logits.detach().argmax(dim=1).cpu().tolist())

        metrics = classification_metrics(targets, predictions, len(self.class_names))
        return {
            "loss": total_loss / len(loader.dataset),
            "accuracy": float(metrics["accuracy"]),
            "macro_f1": float(metrics["macro_f1"]),
        }

    def _complete_checkpoint(
        self,
        epoch: int,
        metrics: dict[str, float],
        train_loader: DataLoader,
    ) -> dict[str, Any]:
        checkpoint = super()._complete_checkpoint(epoch, metrics, train_loader)
        checkpoint["amp_scaler_state"] = self.scaler.state_dict()
        checkpoint["amp_enabled"] = self.amp_enabled
        return checkpoint

    def load_resume(self, checkpoint_path: str | Path, train_loader: DataLoader) -> None:
        super().load_resume(checkpoint_path, train_loader)
        checkpoint = torch.load(checkpoint_path, map_location=self.device, weights_only=False)
        scaler_state = checkpoint.get("amp_scaler_state")
        if scaler_state:
            self.scaler.load_state_dict(scaler_state)
