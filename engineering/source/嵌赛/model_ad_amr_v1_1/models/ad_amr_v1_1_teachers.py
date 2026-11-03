"""Frozen V2/V1 teacher ensemble for V1.1 knowledge distillation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
from torch import nn

from models.ad_amr_net import build_ad_amr_model
from models.qam_aware_rfnet import build_qam_aware_model
from training.utils import resolve_project_path


OLD_CLASSES = ("BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM")


def _freeze(model: nn.Module) -> nn.Module:
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
    return model


def load_v2_teacher(path: str | Path, device: torch.device) -> nn.Module:
    checkpoint = torch.load(resolve_project_path(path), map_location="cpu", weights_only=False)
    classes = tuple(str(v).upper() for v in checkpoint.get("class_names", OLD_CLASSES))
    if classes != OLD_CLASSES:
        raise RuntimeError(f"unexpected V2 class order: {classes}")
    model_cfg: dict[str, Any] = checkpoint.get("config", {}).get("qam_aware", {})
    if not model_cfg:
        raise RuntimeError("V2 checkpoint is missing config.qam_aware")
    variant = "time_power_phase"
    model = build_qam_aware_model(variant, len(classes), **model_cfg)
    model.load_state_dict(checkpoint["model_state"], strict=True)
    return _freeze(model.to(device))


def load_v1_teacher(path: str | Path, device: torch.device) -> nn.Module:
    checkpoint = torch.load(resolve_project_path(path), map_location="cpu", weights_only=False)
    classes = tuple(str(v).upper() for v in checkpoint.get("class_names", OLD_CLASSES))
    if classes != OLD_CLASSES:
        raise RuntimeError(f"unexpected V1 class order: {classes}")
    model = build_ad_amr_model(len(classes))
    model.load_state_dict(checkpoint["model_state"], strict=True)
    return _freeze(model.to(device))


class TeacherEnsemble:
    """Owns frozen teachers; none of these modules is part of the student export."""

    def __init__(self, config: dict[str, Any], device: torch.device) -> None:
        teacher_cfg = config["training"]["distillation"]
        self.enabled = bool(teacher_cfg.get("enabled", True))
        self.temperature = float(teacher_cfg.get("temperature", 3.0))
        self.v2_weight = float(teacher_cfg.get("v2_weight", 0.15))
        self.v1_weight = float(teacher_cfg.get("v1_weight", 0.25))
        self.v2 = load_v2_teacher(config["teachers"]["v2"], device) if self.enabled else None
        v1_paths = list(config["teachers"].get("v1", []))
        self.v1 = [load_v1_teacher(path, device) for path in v1_paths] if self.enabled else []
        if self.enabled and not self.v1:
            raise RuntimeError("distillation is enabled but no V1 teachers were configured")

    def logits(self, iq: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        if not self.enabled or self.v2 is None:
            raise RuntimeError("teacher logits requested while distillation is disabled")
        with torch.inference_mode():
            v2_logits = self.v2(iq).float()
            v1_logits = torch.stack([model(iq)[0].float() for model in self.v1]).mean(dim=0)
        return v2_logits, v1_logits
