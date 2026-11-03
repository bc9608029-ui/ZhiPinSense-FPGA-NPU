"""Explicit FPGA/NPU partition for the frozen TimePowerPhase candidate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch
from torch import nn

from models.qam_aware_rfnet import TimePowerPhaseRFNet
from training.qam_aware_utils import load_qam_aware_config
from training.utils import resolve_project_path


class TimePowerPhaseNPUPartition(nn.Module):
    """NPU-side graph after Power/Lag-1 have been calculated by the FPGA.

    Logical inputs stay separate so that IQ and physical channels may use
    independent INT8 quantization scales.  The learned layers are the exact
    modules from the frozen end-to-end model; no retraining or parameter
    transformation is performed.
    """

    def __init__(self, source: TimePowerPhaseRFNet) -> None:
        super().__init__()
        self.time_branch = source.time_branch
        self.physical_branch = source.physical_branch
        self.classifier = source.classifier

    def forward(self, iq: torch.Tensor, physical_features: torch.Tensor) -> torch.Tensor:
        time_features = self.time_branch(iq)
        physical_embedding = self.physical_branch(physical_features)
        return self.classifier(torch.cat((time_features, physical_embedding), dim=1))


def load_formal_candidate(
    config_path: str | Path = "configs/qam_aware_v2.yaml",
    checkpoint_path: str | Path = "outputs/qam_aware_v2/formal/time_power_phase/checkpoints/best.pt",
) -> tuple[TimePowerPhaseRFNet, dict[str, Any]]:
    """Load the frozen formal candidate without touching any evaluation set."""

    config = load_qam_aware_config(config_path)
    model = TimePowerPhaseRFNet(
        num_classes=len(config["signal"]["modulations"]),
        **config["qam_aware"],
    )
    checkpoint = torch.load(resolve_project_path(checkpoint_path), map_location="cpu", weights_only=False)
    model.load_state_dict(checkpoint["model_state"])
    model.eval()
    return model, checkpoint


def external_physical_features(model: TimePowerPhaseRFNet, iq: torch.Tensor) -> torch.Tensor:
    """Float reference for the FPGA output channel order: [Power, CorrRe, CorrIm]."""

    return model.physical_frontend(iq)
