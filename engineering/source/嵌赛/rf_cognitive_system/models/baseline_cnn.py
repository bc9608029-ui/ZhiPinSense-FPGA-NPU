"""Compact 1-D CNN baseline for [batch, I/Q, samples] input."""

from __future__ import annotations

import torch
from torch import nn


class BaselineCNN(nn.Module):
    def __init__(self, num_classes: int, base_channels: int = 32, dropout: float = 0.1):
        super().__init__()
        c = base_channels
        self.features = nn.Sequential(
            nn.Conv1d(2, c, kernel_size=7, stride=2, padding=3, bias=False),
            nn.BatchNorm1d(c),
            nn.ReLU(inplace=True),
            nn.Conv1d(c, 2 * c, kernel_size=5, stride=2, padding=2, bias=False),
            nn.BatchNorm1d(2 * c),
            nn.ReLU(inplace=True),
            nn.MaxPool1d(kernel_size=2),
            nn.Conv1d(2 * c, 4 * c, kernel_size=3, stride=2, padding=1, bias=False),
            nn.BatchNorm1d(4 * c),
            nn.ReLU(inplace=True),
            nn.AdaptiveAvgPool1d(1),
        )
        self.classifier = nn.Sequential(nn.Flatten(), nn.Dropout(dropout), nn.Linear(4 * c, num_classes))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        if x.ndim != 3 or x.shape[1] != 2:
            raise ValueError(f"Expected [N,2,L] input, received {tuple(x.shape)}")
        return self.classifier(self.features(x))


def model_profile(model: BaselineCNN, sample_length: int) -> dict[str, float | int]:
    """Report parameters, serialized FP32 size, and approximate forward FLOPs."""
    parameters = sum(parameter.numel() for parameter in model.parameters())
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    length = sample_length
    flops = 0
    channels = 2
    for layer in model.features:
        if isinstance(layer, nn.Conv1d):
            out_length = (length + 2 * layer.padding[0] - layer.dilation[0] * (layer.kernel_size[0] - 1) - 1) // layer.stride[0] + 1
            flops += 2 * out_length * layer.out_channels * (channels // layer.groups) * layer.kernel_size[0]
            channels = layer.out_channels
            length = out_length
        elif isinstance(layer, nn.MaxPool1d):
            length = (length - layer.kernel_size) // layer.stride + 1
    linear = next(layer for layer in model.classifier if isinstance(layer, nn.Linear))
    flops += 2 * linear.in_features * linear.out_features
    return {
        "parameters": int(parameters),
        "trainable_parameters": int(trainable),
        "model_size_mb_fp32": float(parameters * 4 / (1024**2)),
        "approx_macs": int(flops // 2),
        "approx_flops": int(flops),
    }
