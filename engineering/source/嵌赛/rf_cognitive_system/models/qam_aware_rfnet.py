"""FPGA-friendly QAM-aware time/physical-feature RF classifiers."""

from __future__ import annotations

import io
from typing import Literal

import torch
from torch import nn

from models.dual_domain_rfnet import FusionClassifier, ResidualBlock1D, TimeFeatureExtractor


QAMVariant = Literal["time_power", "time_phase", "time_power_phase"]


class InstantaneousPower(nn.Module):
    """Compute P[n] = I[n]^2 + Q[n]^2 without complex tensors or sqrt."""

    output_channels = 1

    def forward(self, iq: torch.Tensor) -> torch.Tensor:
        i_component = iq[:, 0:1, :]
        q_component = iq[:, 1:2, :]
        return i_component * i_component + q_component * q_component


class LagOneCorrelation(nn.Module):
    """Real/imaginary parts of x[n] conj(x[n-1]), zero padded at n=0."""

    output_channels = 2

    def forward(self, iq: torch.Tensor) -> torch.Tensor:
        current_i = iq[:, 0:1, 1:]
        current_q = iq[:, 1:2, 1:]
        previous_i = iq[:, 0:1, :-1]
        previous_q = iq[:, 1:2, :-1]
        real = current_i * previous_i + current_q * previous_q
        imaginary = current_q * previous_i - current_i * previous_q
        zero = torch.zeros_like(real[:, :, 0:1])
        return torch.cat((torch.cat((zero, real), dim=2), torch.cat((zero, imaginary), dim=2)), dim=1)


class PowerLagOneFeatures(nn.Module):
    """Concatenate instantaneous power and lag-one real correlation features."""

    output_channels = 3

    def __init__(self) -> None:
        super().__init__()
        self.power = InstantaneousPower()
        self.correlation = LagOneCorrelation()

    def forward(self, iq: torch.Tensor) -> torch.Tensor:
        return torch.cat((self.power(iq), self.correlation(iq)), dim=1)


class StatisticalPooling1D(nn.Module):
    """Concatenate E[x] and E[x^2] for every learned feature channel."""

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        mean = features.mean(dim=-1)
        second_moment = (features * features).mean(dim=-1)
        return torch.cat((mean, second_moment), dim=1)


class PhysicalFeatureEncoder(nn.Module):
    """Small real-valued encoder with learned, label-agnostic scale handling.

    Input BatchNorm absorbs the different numerical scales of power and
    correlation. It uses training-set batch/running statistics only and does
    not receive labels, SNR values, or metadata.
    """

    def __init__(self, input_channels: int, base_channels: int = 8) -> None:
        super().__init__()
        c = int(base_channels)
        self.output_features = 4 * c
        self.network = nn.Sequential(
            nn.BatchNorm1d(input_channels, affine=False),
            nn.Conv1d(input_channels, c, 5, stride=2, padding=2, bias=False),
            nn.BatchNorm1d(c),
            nn.ReLU(inplace=False),
            ResidualBlock1D(c, 2 * c, stride=2),
            ResidualBlock1D(2 * c, 2 * c, stride=2),
            StatisticalPooling1D(),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.network(features)


class _QAMAwareRFNet(nn.Module):
    def __init__(
        self,
        frontend: nn.Module,
        frontend_channels: int,
        num_classes: int,
        time_base_channels: int = 22,
        physical_base_channels: int = 8,
        fusion_features: int = 64,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.physical_frontend = frontend
        self.time_branch = TimeFeatureExtractor(time_base_channels)
        self.physical_branch = PhysicalFeatureEncoder(frontend_channels, physical_base_channels)
        combined = self.time_branch.output_features + self.physical_branch.output_features
        self.classifier = FusionClassifier(combined, fusion_features, num_classes, dropout)

    def forward(self, iq: torch.Tensor) -> torch.Tensor:
        time_features = self.time_branch(iq)
        physical_features = self.physical_branch(self.physical_frontend(iq))
        return self.classifier(torch.cat((time_features, physical_features), dim=1))


class TimePowerRFNet(_QAMAwareRFNet):
    def __init__(self, num_classes: int, **config: object) -> None:
        super().__init__(InstantaneousPower(), 1, num_classes, **config)


class TimePhaseRFNet(_QAMAwareRFNet):
    def __init__(self, num_classes: int, **config: object) -> None:
        super().__init__(LagOneCorrelation(), 2, num_classes, **config)


class TimePowerPhaseRFNet(_QAMAwareRFNet):
    def __init__(self, num_classes: int, **config: object) -> None:
        super().__init__(PowerLagOneFeatures(), 3, num_classes, **config)


def build_qam_aware_model(variant: QAMVariant, num_classes: int, **model_config: object) -> nn.Module:
    classes = {
        "time_power": TimePowerRFNet,
        "time_phase": TimePhaseRFNet,
        "time_power_phase": TimePowerPhaseRFNet,
    }
    if variant not in classes:
        raise ValueError(f"Unknown QAM-aware variant: {variant}")
    return classes[variant](num_classes=num_classes, **model_config)


def qam_aware_model_profile(model: nn.Module, sample_length: int) -> dict[str, float | int | str]:
    """Report learned NN work separately from fixed physical feature work."""
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

    if isinstance(model.physical_frontend, InstantaneousPower):
        feature_multiplications, feature_additions = 2 * sample_length, sample_length
    elif isinstance(model.physical_frontend, LagOneCorrelation):
        feature_multiplications, feature_additions = 4 * (sample_length - 1), 2 * (sample_length - 1)
    else:
        feature_multiplications = 2 * sample_length + 4 * (sample_length - 1)
        feature_additions = sample_length + 2 * (sample_length - 1)

    state_bytes = sum(tensor.numel() * tensor.element_size() for tensor in model.state_dict().values())
    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer)
    return {
        "parameters": int(parameters),
        "trainable_parameters": int(trainable),
        "neural_macs": int(neural_macs),
        "neural_flops": int(2 * neural_macs),
        "physical_frontend_multiplications": int(feature_multiplications),
        "physical_frontend_additions": int(feature_additions),
        "fp32_parameter_size_mb": float(parameters * 4 / (1024**2)),
        "checkpoint_tensor_state_size_mb": float(state_bytes / (1024**2)),
        "serialized_state_dict_mb": float(buffer.tell() / (1024**2)),
        "projected_npu_model_size_mb": float(state_bytes / (1024**2)),
        "hardware_partition_status": "PLANNED ONLY: power/correlation multiply-add frontend is FPGA-suitable; no hardware performance is claimed.",
    }
