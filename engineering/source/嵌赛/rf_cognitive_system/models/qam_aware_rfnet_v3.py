"""Deployable QAM-aware RFNet V3 candidate.

V3 keeps the frozen FPGA/NPU tensor contract used by V2:

* IQ input: ``[N, 2, 1024]`` in ``[I, Q]`` order.
* Physical input: ``[N, 3, 1024]`` in
  ``[power, lag1_real, lag1_imag]`` order.

The network deliberately uses only conventional operators that already occur
in the validated V2 deployment graph (Conv, BatchNorm, ReLU, Add, Concat,
ReduceMean, Mul and Gemm).  It therefore avoids making model accuracy depend on
an unverified Transformer/attention/custom-op implementation.
"""

from __future__ import annotations

import io

import torch
from torch import nn

from models.qam_aware_rfnet import PowerLagOneFeatures


def _round_nearest_away_from_zero(value: torch.Tensor) -> torch.Tensor:
    return torch.where(value >= 0, torch.floor(value + 0.5), torch.ceil(value - 0.5))


class DeploymentInputEmulator(nn.Module):
    """Emulate the frozen Q15 -> FPGA INT8 -> host FP32 input contract.

    The operation is part of training/evaluation only.  It is intentionally
    excluded from :class:`QAMAwareRFNetV3Core`, because real hardware supplies
    these already-quantized planes to the compiled NPU graph.
    """

    def __init__(self) -> None:
        super().__init__()
        self.physical_frontend = PowerLagOneFeatures()

    def forward(self, iq: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        # signed Q15 has the asymmetric endpoint [-32768, 32767].
        q15_counts = _round_nearest_away_from_zero(
            torch.clamp(iq, min=-1.0, max=32767.0 / 32768.0) * 32768.0
        )
        q15 = q15_counts / 32768.0
        iq_int8 = torch.clamp(_round_nearest_away_from_zero(q15_counts * (127.0 / 32768.0)), -127, 127)
        iq_dequantized = iq_int8 / 127.0

        # Q15 products have a Q30 scale.  FPGA quantization uses
        # multiplier=127, shift=31, so dequantized physical planes use 2/127.
        physical_q30 = self.physical_frontend(q15)
        physical_int8 = torch.clamp(
            _round_nearest_away_from_zero(physical_q30 * (127.0 / 2.0)), -127, 127
        )
        physical_dequantized = physical_int8 * (2.0 / 127.0)
        return iq_dequantized, physical_dequantized


class ConvNormAct1D(nn.Sequential):
    """Conv-BN-ReLU block with deployment-friendly explicit padding."""

    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        *,
        stride: int = 1,
    ) -> None:
        if kernel_size % 2 == 0:
            raise ValueError("kernel_size must be odd so temporal alignment is exact")
        super().__init__(
            nn.Conv1d(
                in_channels,
                out_channels,
                kernel_size,
                stride=stride,
                padding=kernel_size // 2,
                bias=False,
            ),
            nn.BatchNorm1d(out_channels),
            nn.ReLU(inplace=False),
        )


class MultiScaleStem1D(nn.Module):
    """Capture symbol-, transition- and short-context structure in parallel."""

    def __init__(
        self,
        in_channels: int,
        branch_channels: int,
        out_channels: int,
        kernels: tuple[int, int, int],
    ) -> None:
        super().__init__()
        self.input_norm = nn.BatchNorm1d(in_channels, affine=False)
        self.branches = nn.ModuleList(
            ConvNormAct1D(in_channels, branch_channels, kernel, stride=2) for kernel in kernels
        )
        self.project = ConvNormAct1D(3 * branch_channels, out_channels, 1)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        normalized = self.input_norm(inputs)
        features = torch.cat([branch(normalized) for branch in self.branches], dim=1)
        return self.project(features)


class ResidualBlockV3(nn.Module):
    """Standard residual block kept simple for reliable INT8 compilation."""

    def __init__(self, in_channels: int, out_channels: int, stride: int = 1) -> None:
        super().__init__()
        self.conv1 = ConvNormAct1D(in_channels, out_channels, 5, stride=stride)
        self.conv2 = nn.Sequential(
            nn.Conv1d(out_channels, out_channels, 3, padding=1, bias=False),
            nn.BatchNorm1d(out_channels),
        )
        self.skip = (
            nn.Identity()
            if stride == 1 and in_channels == out_channels
            else nn.Sequential(
                nn.Conv1d(in_channels, out_channels, 1, stride=stride, bias=False),
                nn.BatchNorm1d(out_channels),
            )
        )
        self.activation = nn.ReLU(inplace=False)

    def forward(self, inputs: torch.Tensor) -> torch.Tensor:
        return self.activation(self.conv2(self.conv1(inputs)) + self.skip(inputs))


class StatisticalPoolingV3(nn.Module):
    """Retain learned first and second moments for QAM discrimination."""

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        mean = features.mean(dim=-1)
        second_moment = (features * features).mean(dim=-1)
        return torch.cat((mean, second_moment), dim=1)


class QAMAwareRFNetV3Core(nn.Module):
    """NPU-side graph accepting the two frozen logical FPGA inputs."""

    def __init__(
        self,
        num_classes: int,
        *,
        iq_branch_channels: int = 12,
        iq_stem_channels: int = 32,
        physical_branch_channels: int = 8,
        physical_stem_channels: int = 24,
        fusion_channels: int = 64,
        stage_channels: tuple[int, int, int] = (64, 96, 128),
        classifier_features: int = 128,
        dropout: float = 0.15,
    ) -> None:
        super().__init__()
        if len(stage_channels) != 3:
            raise ValueError("stage_channels must contain exactly three values")
        self.iq_stem = MultiScaleStem1D(2, iq_branch_channels, iq_stem_channels, (3, 7, 15))
        self.physical_stem = MultiScaleStem1D(
            3, physical_branch_channels, physical_stem_channels, (3, 5, 9)
        )
        self.fusion = ConvNormAct1D(iq_stem_channels + physical_stem_channels, fusion_channels, 1)
        c0, c1, c2 = (int(value) for value in stage_channels)
        self.backbone = nn.Sequential(
            ResidualBlockV3(fusion_channels, c0, stride=2),
            ResidualBlockV3(c0, c0),
            ResidualBlockV3(c0, c1, stride=2),
            ResidualBlockV3(c1, c1),
            ResidualBlockV3(c1, c2, stride=2),
            ResidualBlockV3(c2, c2),
        )
        self.pool = StatisticalPoolingV3()
        # Preserve the low-order physical moments explicitly.  In particular,
        # power first/second moments carry constellation-amplitude information
        # that helps separate 16QAM from 64QAM and should not have to survive
        # every learned strided convolution first.
        self.direct_physical_pool = StatisticalPoolingV3()
        self.direct_physical_norm = nn.BatchNorm1d(6)
        self.classifier = nn.Sequential(
            nn.Linear(2 * c2 + 6, classifier_features),
            nn.ReLU(inplace=False),
            nn.Dropout(float(dropout)),
            nn.Linear(classifier_features, int(num_classes)),
        )

    def forward(self, iq: torch.Tensor, physical_features: torch.Tensor) -> torch.Tensor:
        iq_features = self.iq_stem(iq)
        physical_embedding = self.physical_stem(physical_features)
        fused = self.fusion(torch.cat((iq_features, physical_embedding), dim=1))
        learned = self.pool(self.backbone(fused))
        direct = self.direct_physical_norm(self.direct_physical_pool(physical_features))
        return self.classifier(torch.cat((learned, direct), dim=1))


class QAMAwareRFNetV3(nn.Module):
    """Training graph that computes the frozen physical frontend from IQ."""

    def __init__(self, num_classes: int, **model_config: object) -> None:
        super().__init__()
        self.simulate_hardware_inputs = bool(model_config.pop("simulate_hardware_inputs", True))
        self.physical_frontend = PowerLagOneFeatures()
        self.deployment_emulator = DeploymentInputEmulator()
        self.core = QAMAwareRFNetV3Core(num_classes=num_classes, **model_config)

    def forward(self, iq: torch.Tensor) -> torch.Tensor:
        prepared_iq, physical = self.prepare_inputs(iq)
        return self.core(prepared_iq, physical)

    def prepare_inputs(self, iq: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        if self.simulate_hardware_inputs:
            return self.deployment_emulator(iq)
        return iq, self.physical_frontend(iq)


def build_qam_aware_v3(num_classes: int, **model_config: object) -> QAMAwareRFNetV3:
    return QAMAwareRFNetV3(num_classes=num_classes, **model_config)


def build_qam_aware_v3_partition(source: QAMAwareRFNetV3) -> QAMAwareRFNetV3Core:
    """Return the exact learned NPU graph; parameters are shared, not copied."""

    return source.core


def qam_aware_v3_profile(model: nn.Module, sample_length: int = 1024) -> dict[str, float | int | str]:
    """Profile learned work without counting the fixed FPGA frontend."""

    parameters = sum(parameter.numel() for parameter in model.parameters())
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    macs = 0
    hooks: list[torch.utils.hooks.RemovableHandle] = []

    def count(module: nn.Module, inputs: tuple[torch.Tensor, ...], output: torch.Tensor) -> None:
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
    with torch.inference_mode():
        model(torch.zeros(1, 2, int(sample_length), dtype=torch.float32))
    model.train(was_training)
    for hook in hooks:
        hook.remove()

    state_bytes = sum(tensor.numel() * tensor.element_size() for tensor in model.state_dict().values())
    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer)
    return {
        "parameters": int(parameters),
        "trainable_parameters": int(trainable),
        "neural_macs": int(macs),
        "neural_flops": int(2 * macs),
        "fp32_parameter_size_mb": float(parameters * 4 / (1024**2)),
        "checkpoint_tensor_state_size_mb": float(state_bytes / (1024**2)),
        "serialized_state_dict_mb": float(buffer.tell() / (1024**2)),
        "input_contract": "iq[N,2,1024] + physical[N,3,1024] -> logits[N,8]",
        "operator_policy": "Conv/BatchNorm/ReLU/Add/Concat/ReduceMean/Mul/Gemm only",
    }
