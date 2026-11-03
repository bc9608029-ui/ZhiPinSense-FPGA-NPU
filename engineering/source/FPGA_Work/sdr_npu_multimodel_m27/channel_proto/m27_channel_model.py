"""M27 channel/interference recognition model (spec §十一).

A small CNN built only from NPU/int8-supported operators (Conv2d, ReLU, MaxPool,
Flatten, Linear).  Input [N,2,1024] planar I/Q -> 11 raw logits.  Provides ONNX export
and an int8-feasibility check (every exported ONNX node type must be in the supported
operator whitelist).  This is a *synthetic prototype* model, not a frozen production
model.
"""

from __future__ import annotations

import torch
import torch.nn as nn

from m27_channel_contract import NUM_CHANNEL_LABELS


class ChannelImpairmentNet(nn.Module):
    def __init__(self, n_classes=NUM_CHANNEL_LABELS):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, kernel_size=(1, 3), stride=1, padding=(0, 1)),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=(1, 2)),
            nn.Conv2d(16, 32, kernel_size=(1, 3), stride=1, padding=(0, 1)),
            nn.ReLU(),
            nn.MaxPool2d(kernel_size=(1, 2)),
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(32 * 2 * 256, 64),
            nn.ReLU(),
            nn.Linear(64, n_classes),
        )

    def forward(self, x):
        # x: [N,2,1024] -> add a channel dim for Conv2d
        x = x.unsqueeze(1)                 # [N,1,2,1024]
        x = self.features(x)
        x = self.classifier(x)
        return x                            # [N, n_classes] raw logits


def export_onnx(model, path, dummy_n=1):
    model.eval()
    dummy = torch.zeros(dummy_n, 2, 1024, dtype=torch.float32)
    torch.onnx.export(
        model, dummy, path, input_names=["iq"], output_names=["logits"],
        opset_version=13, do_constant_folding=True, dynamo=False,
    )
    return path


def int8_feasibility(onnx_path, supported_ops):
    """Return (feasible, unsupported_ops).  Checks the ONNX node-type whitelist."""
    import onnx
    model = onnx.load(onnx_path)
    unsupported = set()
    for node in model.graph.node:
        if node.op_type not in supported_ops:
            unsupported.add(node.op_type)
    return (len(unsupported) == 0), sorted(unsupported)
