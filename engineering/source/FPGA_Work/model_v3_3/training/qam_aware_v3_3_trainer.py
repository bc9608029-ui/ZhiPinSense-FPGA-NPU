"""AMP-capable, strictly resumable trainer for QAM-Aware V3.3.

Subclasses the shared resumable trainer with class weights, label smoothing and
gradient clipping, then adds the V3.3 training-only objectives:

* ``residual_penalty_weight`` — L2 penalty on the residual expert's additive
  logit correction ``gate * delta``, keeping the frozen-V2 prediction dominant;
* ``family_aux_loss_weight`` — cross-entropy of the train-only PSK/QAM/FSK/OFDM
  family head (A2);
* ``domain_consistency`` — numeric-domain consistency between the full-precision
  path and the FPGA Mandatory-Core emulated path (A3), MSE on logits by default.

Every one of these is a training/evaluation loss only; none enters the deployed
NPU graph.  The frozen V2 backbone stays in eval mode throughout (the model's
``train()`` override), so its BatchNorm statistics and parameters cannot drift.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as functional
from torch import nn
from torch.utils.data import DataLoader

from models.qam_aware_rfnet_v3_3 import v3_3_family_ids
from training.metrics import classification_metrics
from training.resumable_trainer import ResumableTrainer


class QAMAwareV33Trainer(ResumableTrainer):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        training = self.config["training"]
        model_config = self.config.get("model", {})

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
        self.criterion_family = nn.CrossEntropyLoss()
        self.gradient_clip_norm = float(training.get("gradient_clip_norm", 0.0))
        self.amp_enabled = bool(training.get("amp", True)) and self.device.type == "cuda"
        try:
            self.scaler = torch.amp.GradScaler("cuda", enabled=self.amp_enabled)
        except (AttributeError, TypeError):  # PyTorch 2.0 compatibility.
            self.scaler = torch.cuda.amp.GradScaler(enabled=self.amp_enabled)

        self.residual_penalty_weight = float(training.get("residual_penalty_weight", 0.0))
        self.family_aux_enabled = bool(model_config.get("family_aux", {}).get("enabled", False))
        self.family_aux_loss_weight = float(training.get("family_aux_loss_weight", 0.0))
        self.family_map = (
            v3_3_family_ids(len(self.class_names)).to(self.device)
            if self.family_aux_enabled
            else None
        )
        domain = training.get("domain_consistency", {}) or {}
        self.domain_enabled = bool(domain.get("enabled", False))
        self.domain_weight = float(domain.get("weight", 0.0))
        self.domain_mechanism = str(domain.get("mechanism", "consistency"))
        if self.domain_enabled and self.domain_mechanism != "consistency":
            raise ValueError(
                f"Unsupported domain-consistency mechanism {self.domain_mechanism!r}; "
                "only 'consistency' (MSE logits) is implemented."
            )

        # Candidate label for diagnostics (A0/A1/A2/A3), derived from the flags.
        residual_enabled = bool(model_config.get("residual_expert", {}).get("enabled", True))
        if not residual_enabled:
            self.variant = "A0"
        elif self.domain_enabled:
            self.variant = "A3"
        elif self.family_aux_enabled:
            self.variant = "A2"
        else:
            self.variant = "A1"

    def _family_labels(self, labels: torch.Tensor) -> torch.Tensor:
        return self.family_map[labels]

    def _domain_consistency_loss(self, logits: torch.Tensor, hw_logits: torch.Tensor) -> torch.Tensor:
        # MSE on logits — one mechanism per ablation; CORAL/worst-group are
        # documented as future mechanisms in docs/v3_3_design.md.  The
        # numerical-sensitive part is computed in FP32 to keep the loss stable
        # under AMP (FP16 logits squared would lose precision at the MSE scale).
        return functional.mse_loss(logits.float(), hw_logits.detach().float())

    def _describe_non_finite(
        self,
        *,
        loader: DataLoader,
        batch_index: int,
        inputs: torch.Tensor,
        logits: torch.Tensor,
        ce_loss: torch.Tensor | None,
        family_loss: torch.Tensor | None,
        residual_loss: torch.Tensor | None,
        domain_loss: torch.Tensor | None,
    ) -> str:
        def scalar(value: torch.Tensor | None) -> str:
            if value is None:
                return "n/a"
            return f"{float(value.detach().item()):.6g}"

        seed = self.config.get("seed", "<unset>")
        snr_values = getattr(loader.dataset, "snr_values", None)
        if snr_values is None:
            snr_values = self.config.get("dataset", {}).get("snr_values")
        snr_desc = "n/a"
        if snr_values is not None and len(snr_values) > 0:
            values = [float(value) for value in snr_values]
            snr_desc = f"{min(values):g}..{max(values):g} (n={len(values)})"

        iq_max = float(inputs.detach().abs().max().item())
        physical_max = "n/a"
        moments_max = "n/a"
        expert = getattr(getattr(self.model, "core", None), "expert", None)
        if expert is not None and hasattr(self.model, "prepare_inputs"):
            with torch.no_grad():
                _, physical = self.model.prepare_inputs(inputs)
                physical_max = f"{float(physical.abs().max().item()):.6g}"
                moments = expert.moments(physical)
                moments_max = f"{float(moments.abs().max().item()):.6g}"

        logits_max = float(logits.detach().abs().max().item())
        return "\n".join(
            [
                f"V3.3 training produced a non-finite loss: variant={self.variant} "
                f"seed={seed} epoch={self.current_epoch} batch={batch_index} snr={snr_desc}",
                f"  iq_max_abs={iq_max:.6g} physical_max_abs={physical_max} "
                f"moments_max_abs={moments_max}",
                f"  loss components: ce={scalar(ce_loss)} family={scalar(family_loss)} "
                f"residual={scalar(residual_loss)} domain={scalar(domain_loss)}",
                f"  logits_finite={bool(torch.isfinite(logits).all().item())} "
                f"logits_max_abs={logits_max:.6g}",
            ]
        )

    def _run_epoch(self, loader: DataLoader, training: bool) -> dict[str, float]:
        self.model.train(training)
        total_loss = 0.0
        targets: list[int] = []
        predictions: list[int] = []
        residual_max_abs = 0.0

        for batch_index, batch in enumerate(loader):
            inputs, labels = batch[:2]
            inputs = inputs.to(self.device, non_blocking=True)
            labels = labels.to(self.device, non_blocking=True)
            if training:
                self.optimizer.zero_grad(set_to_none=True)

            ce_loss: torch.Tensor | None = None
            family_loss: torch.Tensor | None = None
            residual_loss: torch.Tensor | None = None
            domain_loss: torch.Tensor | None = None

            with torch.set_grad_enabled(training):
                with torch.autocast(
                    device_type=self.device.type,
                    dtype=torch.float16,
                    enabled=self.amp_enabled,
                ):
                    logits, aux = self.model.forward_with_aux(inputs)
                    ce_loss = self.criterion(logits, labels)
                    loss = ce_loss
                    if self.family_aux_enabled and "family" in aux:
                        family_loss = self.family_aux_loss_weight * self.criterion_family(
                            aux["family"], self._family_labels(labels)
                        )
                        loss = loss + family_loss
                    if self.residual_penalty_weight > 0.0 and "residual" in aux:
                        # FP32 on the numerical-sensitive part: squaring FP16
                        # residuals loses precision at the L2 scale.
                        residual_loss = self.residual_penalty_weight * (
                            aux["residual"].float() ** 2
                        ).mean()
                        loss = loss + residual_loss
                    if self.domain_enabled and training:
                        hw_logits = self.model.forward_domain(inputs, hardware_sim=True)
                        domain_loss = self.domain_weight * self._domain_consistency_loss(
                            logits, hw_logits
                        )
                        loss = loss + domain_loss
                if not torch.isfinite(loss):
                    raise RuntimeError(
                        self._describe_non_finite(
                            loader=loader,
                            batch_index=batch_index,
                            inputs=inputs,
                            logits=logits,
                            ce_loss=ce_loss,
                            family_loss=family_loss,
                            residual_loss=residual_loss,
                            domain_loss=domain_loss,
                        )
                    )
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
            if "residual" in aux:
                residual_max_abs = max(residual_max_abs, float(aux["residual"].detach().abs().max().item()))

        metrics = classification_metrics(targets, predictions, len(self.class_names))
        return {
            "loss": total_loss / len(loader.dataset),
            "accuracy": float(metrics["accuracy"]),
            "macro_f1": float(metrics["macro_f1"]),
            "residual_max_abs": residual_max_abs,
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
        # Same CPU-safe load as ResumableTrainer.load_resume: the AMP scaler state
        # dict is device-free (Python scalars for scale/growth_factor/backoff/
        # growth_interval/growth_tracker), and GradScaler.load_state_dict re-creates
        # its per-device tensors on the right device.  Loading the whole checkpoint
        # on CPU keeps it consistent with the resume path and avoids mapping any
        # RNG/generator tensors onto the GPU a second time.
        checkpoint = torch.load(checkpoint_path, map_location="cpu", weights_only=False)
        scaler_state = checkpoint.get("amp_scaler_state")
        if scaler_state:
            self.scaler.load_state_dict(scaler_state)
