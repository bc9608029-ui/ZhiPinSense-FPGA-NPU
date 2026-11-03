"""NPU-deployable AD-AMR V1.1 student.

The training graph may use losses and frozen teachers with arbitrary operators,
but the deployed classifier intentionally uses only Conv, BatchNormalization,
Relu, Add, ReduceMean, and Gemm from the frozen NPU operator policy.
"""

from __future__ import annotations

import io
from typing import Sequence

import torch
from torch import nn


class ResidualUnit(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, stride: int = 1) -> None:
        super().__init__()
        self.conv1 = nn.Conv1d(in_channels, out_channels, 5, stride=stride, padding=2, bias=False)
        self.bn1 = nn.BatchNorm1d(out_channels)
        self.conv2 = nn.Conv1d(out_channels, out_channels, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm1d(out_channels)
        self.relu = nn.ReLU(inplace=False)
        if stride == 1 and in_channels == out_channels:
            self.projection: nn.Module | None = None
        else:
            self.projection = nn.Sequential(
                nn.Conv1d(in_channels, out_channels, 1, stride=stride, bias=False),
                nn.BatchNorm1d(out_channels),
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = x if self.projection is None else self.projection(x)
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        return self.relu(out + residual)


class DeployableResidualDenoiser(nn.Module):
    """Shape-preserving residual denoiser without Resize/Sigmoid/Abs/Sign."""

    def __init__(self, channels: int = 24, blocks: int = 3) -> None:
        super().__init__()
        self.stem = nn.Sequential(
            nn.Conv1d(2, channels, 7, padding=3, bias=False),
            nn.BatchNorm1d(channels),
            nn.ReLU(inplace=False),
        )
        self.blocks = nn.Sequential(*[ResidualUnit(channels, channels) for _ in range(blocks)])
        self.correction = nn.Conv1d(channels, 2, 5, padding=2, bias=False)

    def forward(self, iq: torch.Tensor) -> torch.Tensor:
        correction = self.correction(self.blocks(self.stem(iq)))
        return iq + correction


class ADAMRV11Net(nn.Module):
    def __init__(
        self,
        num_classes: int = 10,
        denoiser_channels: int = 24,
        denoiser_blocks: int = 3,
        feature_channels: Sequence[int] = (32, 48, 64, 96),
        classifier_hidden: int = 128,
        dropout: float = 0.15,
    ) -> None:
        super().__init__()
        if num_classes < 2:
            raise ValueError("num_classes must be at least two")
        if not feature_channels:
            raise ValueError("feature_channels must not be empty")
        self.num_classes = int(num_classes)
        self.denoiser = DeployableResidualDenoiser(denoiser_channels, denoiser_blocks)
        stages: list[nn.Module] = []
        in_channels = 2
        for channels in feature_channels:
            stages.append(ResidualUnit(in_channels, int(channels), stride=2))
            stages.append(ResidualUnit(int(channels), int(channels), stride=1))
            in_channels = int(channels)
        self.features = nn.Sequential(*stages)
        self.classifier = nn.Sequential(
            nn.Linear(in_channels, classifier_hidden),
            nn.ReLU(inplace=False),
            nn.Dropout(dropout),
            nn.Linear(classifier_hidden, num_classes),
        )

    def forward(self, iq: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        denoised = self.denoiser(iq)
        features = self.features(denoised).mean(dim=-1)
        return self.classifier(features), denoised


class ADAMRV11Classifier(nn.Module):
    def __init__(self, model: ADAMRV11Net) -> None:
        super().__init__()
        self.model = model

    def forward(self, iq: torch.Tensor) -> torch.Tensor:
        logits, _ = self.model(iq)
        return logits


def build_ad_amr_v1_1_model(num_classes: int, **config: object) -> ADAMRV11Net:
    allowed = {
        "denoiser_channels", "denoiser_blocks", "feature_channels",
        "classifier_hidden", "dropout",
    }
    return ADAMRV11Net(num_classes=num_classes, **{k: v for k, v in config.items() if k in allowed})


def profile_ad_amr_v1_1(model: nn.Module, sample_length: int) -> dict[str, float | int | str]:
    parameters = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    macs = 0
    hooks = []

    def count(module: nn.Module, _inputs: tuple[torch.Tensor, ...], output: torch.Tensor) -> None:
        nonlocal macs
        if isinstance(module, nn.Conv1d):
            macs += int(output.numel() * (module.in_channels // module.groups) * module.kernel_size[0])
        elif isinstance(module, nn.Linear):
            macs += int(output.numel() * module.in_features)

    for module in model.modules():
        if isinstance(module, (nn.Conv1d, nn.Linear)):
            hooks.append(module.register_forward_hook(count))
    was_training = model.training
    model.eval()
    reference = next(model.parameters())
    with torch.inference_mode():
        model(torch.zeros(1, 2, sample_length, device=reference.device, dtype=reference.dtype))
    model.train(was_training)
    for hook in hooks:
        hook.remove()
    state_bytes = sum(t.numel() * t.element_size() for t in model.state_dict().values())
    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer)
    return {
        "parameters": int(parameters),
        "trainable_parameters": int(trainable),
        "neural_macs": int(macs),
        "neural_flops": int(2 * macs),
        "fp32_parameter_size_mb": float(parameters * 4 / 1024**2),
        "state_dict_size_mb": float(state_bytes / 1024**2),
        "serialized_state_dict_mb": float(buffer.tell() / 1024**2),
        "input_contract": f"iq[N,2,{sample_length}] -> logits[N,{getattr(model, 'num_classes', '?')}]",
        "operator_policy": "Conv/BatchNormalization/Relu/Add/ReduceMean/Gemm only",
    }
