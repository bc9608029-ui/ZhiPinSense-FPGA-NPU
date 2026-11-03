"""Outlier Exposure + Energy trainer for the strict 24-class model.

Subclasses ``RML24Trainer`` and replaces the training CE loss with the
OE+Energy loss when ``oe_energy.enabled`` is true.  The auxiliary OOD family is
pre-generated once (deterministically) from ``oe_aux_train`` and strictly
isolated from the final OOD test family (``ood_final_test``), so the Energy
score is never tuned on the family it is finally measured against.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from datasets.ood_dataset import OOD_FAMILIES, default_ood_signal_config, generate_ood_records
from training.ad_amr_v1_1_trainer import _summary
from training.oe_energy_loss import oe_energy_loss
from training.rml24_trainer import RML24Trainer

_FAMILY_ALIASES = {"near": "near_24", "far": "far", "ambiguous": "ambiguous"}


class OETrainer(RML24Trainer):
    def __init__(self, config: dict[str, Any], paths: dict[str, Path],
                 classes: list[str]) -> None:
        super().__init__(config, paths, classes)
        oe = config.get("oe_energy", {})
        self.oe_enabled = bool(oe.get("enabled", False))
        self.temperature = float(oe.get("temperature", 1.0))
        self.margin_in = float(oe.get("margin_in", 0.0))
        self.margin_out = float(oe.get("margin_out", -10.0))
        self.lambda_ = float(oe.get("lambda", 0.1))
        self._ood_tensor: torch.Tensor | None = None
        self._ood_idx = 0
        if self.oe_enabled:
            self._ood_tensor = self._build_ood_tensor(config)

    @staticmethod
    def _resolve_family(name: str) -> str:
        if name in OOD_FAMILIES:
            return name
        if name in _FAMILY_ALIASES:
            return _FAMILY_ALIASES[name]
        raise ValueError(f"unknown oe_family {name!r}; expected {sorted(set(OOD_FAMILIES) | set(_FAMILY_ALIASES))}")

    def _build_ood_tensor(self, config: dict[str, Any]) -> torch.Tensor:
        oe = config["oe_energy"]
        family = self._resolve_family(str(oe.get("oe_family", "near")))
        count = int(oe.get("oe_count_per_modulation", 4096))
        records = generate_ood_records(
            family, "oe_aux_train", seed=int(config["seed"]),
            count_per_modulation=count,
            signal_config=dict(config.get("signal", default_ood_signal_config())),
        )
        return torch.from_numpy(records.planar)  # [N, 2, 1024] float32

    def _ood_batch(self, batch_size: int, device: torch.device) -> torch.Tensor:
        tensor = self._ood_tensor
        if tensor is None:
            raise RuntimeError("OOD tensor is unavailable while oe_energy.enabled is false")
        n = tensor.shape[0]
        stop = self._ood_idx + batch_size
        if stop <= n:
            chunk = tensor[self._ood_idx:stop]
        else:
            chunk = torch.cat([tensor[self._ood_idx:], tensor[:stop - n]], dim=0)
        self._ood_idx = stop % n
        return chunk.to(device, non_blocking=True)

    def _run_epoch(self, loader: DataLoader, training: bool) -> dict[str, Any]:
        if not (training and self.oe_enabled):
            return super()._run_epoch(loader, training)

        self.model.train(True)
        self._ood_idx = 0
        total_loss = 0.0
        total_count = 0
        targets: list[int] = []
        predictions: list[int] = []
        snrs: list[float] = []
        for batch in loader:
            noisy = batch["noisy_iq"].to(self.device, non_blocking=True)
            labels = batch["label"].to(self.device, non_blocking=True)
            snr_db = batch["snr_db"].to(self.device, non_blocking=True)
            ood = self._ood_batch(int(labels.numel()), self.device)
            with torch.autocast(device_type=self.device.type, dtype=self.amp_dtype,
                                enabled=self.amp_enabled):
                logits, _ = self.model(noisy)
                logits_ood, _ = self.model(ood)
                loss, _components = oe_energy_loss(
                    logits, labels, logits_ood, temperature=self.temperature,
                    margin_in=self.margin_in, margin_out=self.margin_out, lambda_=self.lambda_,
                )
            if not bool(torch.isfinite(loss)):
                raise RuntimeError(
                    f"OE non-finite loss epoch={len(self.history)+1} "
                    f"snr=[{snr_db.min().item()},{snr_db.max().item()}]"
                )
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


__all__ = ["OETrainer"]
