"""QAM-aware RFNet V3.1 candidate — V3 core plus higher-order QAM moments.

V3.1 keeps the exact frozen FPGA/NPU tensor contract used by V2 and V3:

* IQ input: ``[N, 2, 1024]`` in ``[I, Q]`` order.
* Physical input: ``[N, 3, 1024]`` in ``[power, lag1_real, lag1_imag]`` order.

The only change relative to V3 is the *direct physical shortcut*: instead of
only first/second moments, it now retains moments 1..``physical_moment_order``
of the raw power and lag-one correlation planes.  Higher-order power moments
(skewness/kurtosis of the amplitude distribution) separate 16QAM (4 amplitude
rings) from 64QAM (8 amplitude rings) without adding any operator outside the
already-validated V2/V3 deployment set (Mul + ReduceMean + Concat + Gemm).
"""

from __future__ import annotations

import io

import torch
from torch import nn

from models.qam_aware_rfnet import PowerLagOneFeatures
from models.qam_aware_rfnet_v3 import (
    ConvNormAct1D,
    DeploymentInputEmulator,
    MultiScaleStem1D,
    ResidualBlockV3,
    StatisticalPoolingV3,
)


class HigherOrderMomentPool(nn.Module):
    """Concatenate ``E[x], E[x^2], ..., E[x^order]`` for every feature channel.

    Implemented only with element-wise multiplication and a temporal mean, so it
    compiles to Mul/ReduceMean/Concat on the ZG330 NPU.  ``order=2`` reproduces
    :class:`StatisticalPoolingV3` exactly.
    """

    def __init__(self, order: int = 4) -> None:
        super().__init__()
        if int(order) < 1:
            raise ValueError("order must be >= 1")
        self.order = int(order)

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        current = features
        moments = [current.mean(dim=-1)]
        for _ in range(1, self.order):
            current = current * features
            moments.append(current.mean(dim=-1))
        return torch.cat(moments, dim=1)


class QAMAwareRFNetV31Core(nn.Module):
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
        physical_moment_order: int = 4,
    ) -> None:
        super().__init__()
        if len(stage_channels) != 3:
            raise ValueError("stage_channels must contain exactly three values")
        if int(physical_moment_order) < 2:
            raise ValueError("physical_moment_order must be >= 2")
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
        # Higher-order raw moments: amplitude-distribution shape (skewness,
        # kurtosis) is the strongest NPU-deployable 16QAM/64QAM discriminator.
        moment_order = int(physical_moment_order)
        direct_features = 3 * moment_order
        self.direct_physical_pool = HigherOrderMomentPool(moment_order)
        self.direct_physical_norm = nn.BatchNorm1d(direct_features)
        self.classifier = nn.Sequential(
            nn.Linear(2 * c2 + direct_features, classifier_features),
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


class QAMAwareRFNetV31(nn.Module):
    """Training graph that computes the frozen physical frontend from IQ."""

    def __init__(self, num_classes: int, **model_config: object) -> None:
        super().__init__()
        self.simulate_hardware_inputs = bool(model_config.pop("simulate_hardware_inputs", True))
        self.physical_frontend = PowerLagOneFeatures()
        self.deployment_emulator = DeploymentInputEmulator()
        self.core = QAMAwareRFNetV31Core(num_classes=num_classes, **model_config)

    def forward(self, iq: torch.Tensor) -> torch.Tensor:
        prepared_iq, physical = self.prepare_inputs(iq)
        return self.core(prepared_iq, physical)

    def prepare_inputs(self, iq: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        if self.simulate_hardware_inputs:
            return self.deployment_emulator(iq)
        return iq, self.physical_frontend(iq)


def build_qam_aware_v3_1(num_classes: int, **model_config: object) -> QAMAwareRFNetV31:
    return QAMAwareRFNetV31(num_classes=num_classes, **model_config)


def build_qam_aware_v3_1_partition(source: QAMAwareRFNetV31) -> QAMAwareRFNetV31Core:
    """Return the exact learned NPU graph; parameters are shared, not copied."""

    return source.core


def qam_aware_v3_1_profile(model: nn.Module, sample_length: int = 1024) -> dict[str, float | int | str]:
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
