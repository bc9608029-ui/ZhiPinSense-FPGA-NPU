"""Lightweight, ONNX-friendly time/frequency ablation models for RF IQ."""

from __future__ import annotations

import io
import math
from typing import Literal

import torch
import torch.nn.functional as functional
from torch import nn


VariantName = Literal["time_only", "frequency_only", "time_only_wide", "dual", "dual_domain"]


class ResidualBlock1D(nn.Module):
    """Two standard convolutions with an optional projected residual."""

    def __init__(self, in_channels: int, out_channels: int, stride: int = 1) -> None:
        super().__init__()
        self.conv1 = nn.Conv1d(in_channels, out_channels, 5, stride=stride, padding=2, bias=False)
        self.bn1 = nn.BatchNorm1d(out_channels)
        self.conv2 = nn.Conv1d(out_channels, out_channels, 3, padding=1, bias=False)
        self.bn2 = nn.BatchNorm1d(out_channels)
        self.skip = (
            nn.Identity()
            if stride == 1 and in_channels == out_channels
            else nn.Sequential(nn.Conv1d(in_channels, out_channels, 1, stride=stride, bias=False), nn.BatchNorm1d(out_channels))
        )
        self.activation = nn.ReLU(inplace=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        residual = self.skip(x)
        x = self.activation(self.bn1(self.conv1(x)))
        x = self.bn2(self.conv2(x))
        return self.activation(x + residual)


class FixedDFTLogPower(nn.Module):
    """Framed complex FFT-equivalent log-power using exportable real matrix ops.

    A fixed real DFT is used because native complex FFT export is not consistently
    supported by NPU ONNX toolchains. It is numerically equivalent to an FFT and
    can later be replaced by FPGA FFT output without changing the frequency CNN.
    """

    def __init__(self, fft_length: int = 256) -> None:
        super().__init__()
        if fft_length <= 0:
            raise ValueError("fft_length must be positive")
        self.fft_length = int(fft_length)
        bins = torch.arange(self.fft_length, dtype=torch.float32).unsqueeze(1)
        samples = torch.arange(self.fft_length, dtype=torch.float32).unsqueeze(0)
        angle = 2.0 * math.pi * bins * samples / self.fft_length
        self.register_buffer("cosine", torch.cos(angle))
        self.register_buffer("sine", torch.sin(angle))

    def forward(self, iq: torch.Tensor) -> torch.Tensor:
        if iq.ndim != 3 or iq.shape[1] != 2:
            raise ValueError(f"Expected [N,2,L] input, received {tuple(iq.shape)}")
        if iq.shape[-1] % self.fft_length != 0:
            raise ValueError("IQ length must be divisible by fft_length")
        frames = iq.reshape(iq.shape[0], 2, -1, self.fft_length)
        i_component, q_component = frames[:, 0], frames[:, 1]
        real = functional.linear(i_component, self.cosine) + functional.linear(q_component, self.sine)
        imag = functional.linear(q_component, self.cosine) - functional.linear(i_component, self.sine)
        power = (real.square() + imag.square()) / float(self.fft_length)
        mean_power = power.mean(dim=1)
        shifted = torch.roll(mean_power, shifts=self.fft_length // 2, dims=-1)
        return torch.log1p(torch.clamp_min(shifted, 0.0)).unsqueeze(1)

    def extra_macs(self, sample_length: int) -> int:
        frames = sample_length // self.fft_length
        return int(4 * frames * self.fft_length * self.fft_length)


class TimeFeatureExtractor(nn.Module):
    def __init__(self, base_channels: int = 16) -> None:
        super().__init__()
        c = base_channels
        self.output_features = 4 * c
        self.network = nn.Sequential(
            nn.Conv1d(2, c, 7, stride=2, padding=3, bias=False),
            nn.BatchNorm1d(c),
            nn.ReLU(inplace=False),
            ResidualBlock1D(c, 2 * c, stride=2),
            ResidualBlock1D(2 * c, 4 * c, stride=2),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )

    def forward(self, iq: torch.Tensor) -> torch.Tensor:
        return self.network(iq)


class FrequencyFeatureExtractor(nn.Module):
    def __init__(self, base_channels: int = 16, fft_length: int = 256) -> None:
        super().__init__()
        c = base_channels
        self.output_features = 4 * c
        self.spectrum = FixedDFTLogPower(fft_length)
        self.network = nn.Sequential(
            nn.Conv1d(1, c, 7, stride=2, padding=3, bias=False),
            nn.BatchNorm1d(c),
            nn.ReLU(inplace=False),
            ResidualBlock1D(c, 2 * c, stride=2),
            ResidualBlock1D(2 * c, 4 * c, stride=2),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
        )

    def forward(self, iq: torch.Tensor) -> torch.Tensor:
        return self.network(self.spectrum(iq))


class FusionClassifier(nn.Module):
    def __init__(self, input_features: int, fusion_features: int, num_classes: int, dropout: float) -> None:
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(input_features, fusion_features),
            nn.ReLU(inplace=False),
            nn.Dropout(dropout),
            nn.Linear(fusion_features, num_classes),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.network(features)


class TimeOnlyRFNet(nn.Module):
    def __init__(self, num_classes: int, base_channels: int = 16, fusion_features: int = 64, dropout: float = 0.1, **_: object) -> None:
        super().__init__()
        self.time_branch = TimeFeatureExtractor(base_channels)
        self.classifier = FusionClassifier(self.time_branch.output_features, fusion_features, num_classes, dropout)

    def forward(self, iq: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.time_branch(iq))


class TimeOnlyWideRFNet(nn.Module):
    """Capacity-matched time-only control for the dual-branch model."""

    def __init__(
        self,
        num_classes: int,
        wide_base_channels: int = 23,
        fusion_features: int = 64,
        dropout: float = 0.1,
        **_: object,
    ) -> None:
        super().__init__()
        self.time_branch = TimeFeatureExtractor(wide_base_channels)
        self.classifier = FusionClassifier(self.time_branch.output_features, fusion_features, num_classes, dropout)

    def forward(self, iq: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.time_branch(iq))


class FrequencyOnlyRFNet(nn.Module):
    def __init__(self, num_classes: int, base_channels: int = 16, fusion_features: int = 64, dropout: float = 0.1, fft_length: int = 256, **_: object) -> None:
        super().__init__()
        self.frequency_branch = FrequencyFeatureExtractor(base_channels, fft_length)
        self.classifier = FusionClassifier(self.frequency_branch.output_features, fusion_features, num_classes, dropout)

    def forward(self, iq: torch.Tensor) -> torch.Tensor:
        return self.classifier(self.frequency_branch(iq))


class DualDomainRFNet(nn.Module):
    def __init__(self, num_classes: int, base_channels: int = 16, fusion_features: int = 64, dropout: float = 0.1, fft_length: int = 256, **_: object) -> None:
        super().__init__()
        self.time_branch = TimeFeatureExtractor(base_channels)
        self.frequency_branch = FrequencyFeatureExtractor(base_channels, fft_length)
        combined = self.time_branch.output_features + self.frequency_branch.output_features
        self.classifier = FusionClassifier(combined, fusion_features, num_classes, dropout)

    def forward(self, iq: torch.Tensor) -> torch.Tensor:
        features = torch.cat((self.time_branch(iq), self.frequency_branch(iq)), dim=1)
        return self.classifier(features)


def build_ablation_model(variant: VariantName, num_classes: int, **model_config: object) -> nn.Module:
    classes = {
        "time_only": TimeOnlyRFNet,
        "frequency_only": FrequencyOnlyRFNet,
        "time_only_wide": TimeOnlyWideRFNet,
        "dual": DualDomainRFNet,
        "dual_domain": DualDomainRFNet,
    }
    if variant not in classes:
        raise ValueError(f"Unknown ablation variant: {variant}")
    return classes[variant](num_classes=num_classes, **model_config)


def ablation_model_profile(model: nn.Module, sample_length: int) -> dict[str, float | int | str]:
    """Separate planned FPGA frontend work from neural-network complexity."""
    parameters = sum(parameter.numel() for parameter in model.parameters())
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    neural_macs = 0
    hooks = []

    def count(module: nn.Module, inputs: tuple[torch.Tensor, ...], output: torch.Tensor) -> None:
        nonlocal neural_macs
        if isinstance(module, nn.Conv1d):
            neural_macs += int(output.numel() * (module.in_channels // module.groups) * module.kernel_size[0])
        elif isinstance(module, nn.Linear):
            neural_macs += int(output.numel() * module.in_features)

    for module in model.modules():
        if isinstance(module, (nn.Conv1d, nn.Linear)):
            hooks.append(module.register_forward_hook(count))
    was_training = model.training
    model.eval()
    with torch.inference_mode():
        model(torch.zeros(1, 2, sample_length))
    model.train(was_training)
    for hook in hooks:
        hook.remove()
    frontend_macs = 0
    frontend_state_bytes = 0
    frontend_state_elements = 0
    for module in model.modules():
        if isinstance(module, FixedDFTLogPower):
            frontend_macs += module.extra_macs(sample_length)
            for tensor in (module.cosine, module.sine):
                frontend_state_elements += tensor.numel()
                frontend_state_bytes += tensor.numel() * tensor.element_size()
    state_bytes = sum(tensor.numel() * tensor.element_size() for tensor in model.state_dict().values())
    state_elements = sum(tensor.numel() for tensor in model.state_dict().values())
    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer)
    total_macs = neural_macs + frontend_macs
    return {
        "parameters": int(parameters),
        "trainable_parameters": int(trainable),
        "parameter_size_mb_fp32": float(parameters * 4 / (1024**2)),
        "fixed_non_trainable_state_elements": int(state_elements - parameters),
        "fixed_non_trainable_state_mb": float((state_bytes - parameters * 4) / (1024**2)),
        "frontend_fixed_state_elements": int(frontend_state_elements),
        "frontend_fixed_state_mb": float(frontend_state_bytes / (1024**2)),
        "neural_macs": int(neural_macs),
        "neural_flops": int(2 * neural_macs),
        "frontend_macs_pc_reference": int(frontend_macs),
        "frontend_flops_pc_reference": int(2 * frontend_macs),
        "total_software_macs": int(total_macs),
        "total_software_flops": int(2 * total_macs),
        "checkpoint_tensor_state_size_mb": float(state_bytes / (1024**2)),
        "serialized_state_dict_mb": float(buffer.tell() / (1024**2)),
        "projected_npu_model_size_mb": float((state_bytes - frontend_state_bytes) / (1024**2)),
        "hardware_partition_status": "PLANNED ONLY: fixed DFT/power frontend is intended for FPGA; no hardware performance is claimed.",
        "approx_macs": int(total_macs),
        "approx_flops": int(2 * total_macs),
    }
