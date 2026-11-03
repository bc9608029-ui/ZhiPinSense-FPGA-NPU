"""RadioML2018.01A 24-class head wrapper around the shared ADAMRV11Net.

The network is unchanged (reused verbatim from ``models.ad_amr_v1_1_net``); this
module only pins ``num_classes=24`` and the 24-class contract so training,
evaluation, and export share one builder.
"""

from __future__ import annotations

from typing import Any

import torch
from torch import nn

from contracts.rml24_contract import LABEL_ORDER_24, assert_24class_order
from models.ad_amr_v1_1_net import ADAMRV11Classifier, ADAMRV11Net, build_ad_amr_v1_1_model


def build_rml24_model(num_classes: int = len(LABEL_ORDER_24), **config: Any) -> ADAMRV11Net:
    if int(num_classes) != len(LABEL_ORDER_24):
        raise ValueError(f"24-class contract requires num_classes={len(LABEL_ORDER_24)}, got {num_classes}")
    return build_ad_amr_v1_1_model(int(num_classes), **config)


class RML24Classifier(nn.Module):
    """Logits-only wrapper (raw logits, no softmax) for ONNX export / OOD scoring."""

    def __init__(self, model: ADAMRV11Net) -> None:
        super().__init__()
        self.model = model

    def forward(self, iq: torch.Tensor) -> torch.Tensor:
        logits, _ = self.model(iq)
        return logits


__all__ = [
    "build_rml24_model", "RML24Classifier", "LABEL_ORDER_24", "assert_24class_order",
]
