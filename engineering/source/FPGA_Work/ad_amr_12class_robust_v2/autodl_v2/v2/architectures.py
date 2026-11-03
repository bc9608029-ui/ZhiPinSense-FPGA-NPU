"""Phase-C lightweight architecture candidates (NPU-operator compatible).

Every candidate here reuses V1's ResidualUnit / DeployableResidualDenoiser and
stays within the frozen NPU operator policy (Conv, BatchNormalization, Relu,
Add, ReduceMean, Gemm).  GRU/LSTM "recurrent" candidates are intentionally
excluded because they introduce operators outside that policy and would yield
a non-deployable graph.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

import torch
from torch import nn

from models.ad_amr_v1_1_net import ADAMRV11Net, DeployableResidualDenoiser, ResidualUnit, build_ad_amr_v1_1_model


class _StemK9Net(ADAMRV11Net):
    """Baseline net with a wider denoiser stem kernel (7 -> 9)."""

    def __init__(self, num_classes: int = 10, denoiser_channels: int = 24,
                 denoiser_blocks: int = 3, feature_channels: Sequence[int] = (32, 48, 64, 96),
                 classifier_hidden: int = 128, dropout: float = 0.15) -> None:
        super().__init__(num_classes, denoiser_channels, denoiser_blocks,
                         feature_channels, classifier_hidden, dropout)
        self.denoiser.stem = nn.Sequential(
            nn.Conv1d(2, denoiser_channels, 9, padding=4, bias=False),
            nn.BatchNorm1d(denoiser_channels),
            nn.ReLU(inplace=False),
        )


CANDIDATE_INFO: dict[str, dict[str, Any]] = {
    "v1_baseline": {"description": "V1 ADAMRV11Net (Phase A reference)", "deployable": True},
    "deep_features": {"description": "5-stage features [32,48,64,96,128]", "deployable": True},
    "wide_features": {"description": "wide features [48,64,96,128]", "deployable": True},
    "extra_block": {"description": "5 residual denoiser blocks", "deployable": True},
    "narrow_head": {"description": "classifier hidden 128 -> 64", "deployable": True},
    "stem_k9": {"description": "denoiser stem kernel 7 -> 9", "deployable": True},
}


def build_candidate(name: str, num_classes: int, **model_cfg: Any) -> nn.Module:
    """Build a named Phase-C candidate from a frozen model config dict."""
    if name not in CANDIDATE_INFO:
        raise ValueError(f"unknown candidate {name!r}; expected {sorted(CANDIDATE_INFO)}")
    cfg = dict(model_cfg)
    if name == "v1_baseline":
        return build_ad_amr_v1_1_model(num_classes, **cfg)
    if name == "deep_features":
        cfg["feature_channels"] = [32, 48, 64, 96, 128]
        return build_ad_amr_v1_1_model(num_classes, **cfg)
    if name == "wide_features":
        cfg["feature_channels"] = [48, 64, 96, 128]
        return build_ad_amr_v1_1_model(num_classes, **cfg)
    if name == "extra_block":
        cfg["denoiser_blocks"] = 5
        return build_ad_amr_v1_1_model(num_classes, **cfg)
    if name == "narrow_head":
        cfg["classifier_hidden"] = 64
        return build_ad_amr_v1_1_model(num_classes, **cfg)
    if name == "stem_k9":
        return _StemK9Net(num_classes, **cfg)
    raise ValueError(name)
