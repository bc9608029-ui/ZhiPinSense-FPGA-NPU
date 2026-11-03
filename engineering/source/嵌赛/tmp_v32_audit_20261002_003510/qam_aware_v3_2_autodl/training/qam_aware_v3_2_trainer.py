"""Knowledge-distilling, strictly resumable trainer for QAM-Aware V3.2.

Extends the AMP-capable V3 trainer (class weights, label smoothing, gradient
clipping) with a frozen V2 teacher.  The total loss is::

    loss = CrossEntropy(student_logits, y)
         + alpha * T^2 * KL(softmax(student_logits/T), softmax(teacher_logits/T))

At initialization student == teacher, so the KL term starts at zero and only
grows to the extent the zero-gated delta branch genuinely improves the fit.  The
teacher is never a parameter of the student, never appears in the student
``state_dict``, and is never exported to ONNX.
"""

from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as functional
from torch import nn
from torch.utils.data import DataLoader

from training.qam_aware_v3_trainer import QAMAwareV3Trainer


class QAMAwareV32Trainer(QAMAwareV3Trainer):
    def __init__(self, *args: Any, teacher: nn.Module | None = None, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        distillation = self.config["training"].get("distillation", {})
        self.distill_enabled = bool(distillation.get("enabled", False))
        self.temperature = float(distillation.get("temperature", 4.0))
        self.alpha = float(distillation.get("alpha", 0.7))
        self.teacher = teacher
        if self.distill_enabled and self.teacher is None:
            raise ValueError("Distillation is enabled but no teacher model was provided.")
        if self.teacher is not None:
            self.teacher.to(self.device).eval()
            for parameter in self.teacher.parameters():
                parameter.requires_grad_(False)

    def _distillation_loss(self, student_logits: torch.Tensor, teacher_logits: torch.Tensor) -> torch.Tensor:
        temperature = self.temperature
        student_log_prob = functional.log_softmax(student_logits / temperature, dim=1)
        teacher_prob = functional.softmax(teacher_logits / temperature, dim=1)
        kld = functional.kl_div(student_log_prob, teacher_prob, reduction="batchmean")
        return self.alpha * (temperature**2) * kld

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
                    if self.distill_enabled:
                        with torch.no_grad():
                            teacher_logits = self.teacher(inputs)
                        loss = loss + self._distillation_loss(logits, teacher_logits)
                if not torch.isfinite(loss):
                    raise RuntimeError("V3.2 training produced a non-finite loss")
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

        from training.metrics import classification_metrics

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
        checkpoint["distillation"] = {
            "enabled": self.distill_enabled,
            "temperature": self.temperature,
            "alpha": self.alpha,
            "teacher_present": self.teacher is not None,
        }
        return checkpoint
