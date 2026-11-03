"""QAM-Aware RFNet V3.2 — frozen V2 backbone + zero-gated QAM delta branch.

V3.2 inverts V3.1's failure mode.  It keeps the frozen V2 ``TimePowerPhaseRFNet``
backbone intact (its logits are computed on the exact same path) and adds a small,
separate, **zero-gated** higher-order-moment branch that can only *additively*
correct the V2 logits:

    logits = v2_logits + gate * delta_logits,   gate = 0 at initialization.

The delta branch reuses V3.1's proven ``HigherOrderMomentPool`` (raw
``E[x], E[x^2], E[x^3], E[x^4]`` of the physical planes), which is the one
result from V3.1 that was genuinely useful — a strong 16QAM/64QAM amplitude-ring
discriminator.  Everything V3.1 got wrong (capacity explosion, QAM class
reweighting of a monolithic classifier, 64QAM over-prediction) is excluded.

Two deployability substitutions make the V2 backbone clean under the eight-operator
NPU policy, without changing any learned parameter or ``state_dict`` key:

* ``AdaptiveAvgPool1d(1)`` + ``Flatten``  -> ``mean(dim=-1)`` (``ReduceMean``);
* ``BatchNorm1d(3, affine=False)``        -> ``BatchNorm1d(3, affine=True)`` frozen
  at unit scale / zero bias (exports as initializers, not ``Constant`` nodes).

The frozen input contract is unchanged: ``iq`` FP32 ``[N,2,1024]`` and
``physical_features`` FP32 ``[N,3,1024]`` in ``[power, lag1_real, lag1_imag]``
order.
"""

from __future__ import annotations

import io

import torch
from torch import nn

from models.dual_domain_rfnet import FusionClassifier, ResidualBlock1D
from models.qam_aware_rfnet import PowerLagOneFeatures, StatisticalPooling1D
from models.qam_aware_rfnet_v3 import DeploymentInputEmulator
from models.qam_aware_rfnet_v3_1 import HigherOrderMomentPool


class MeanPool1D(nn.Module):
    """Global temporal mean replacing ``AdaptiveAvgPool1d(1)`` + ``Flatten``.

    V2's global average pool exports as ``GlobalAveragePool`` + ``Flatten``,
    outside the eight-operator NPU policy.  A plain ``mean(dim=-1)`` produces the
    identical ``[N, C]`` result and exports as ``ReduceMean``.  It has no
    parameters, so the V2 ``state_dict`` keys are unchanged.
    """

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return features.mean(dim=-1)


class DeployableTimeFeatureExtractor(nn.Module):
    """V2 ``TimeFeatureExtractor`` with the global pool replaced by ``ReduceMean``."""

    def __init__(self, base_channels: int = 16) -> None:
        super().__init__()
        c = int(base_channels)
        self.output_features = 4 * c
        self.network = nn.Sequential(
            nn.Conv1d(2, c, 7, stride=2, padding=3, bias=False),
            nn.BatchNorm1d(c),
            nn.ReLU(inplace=False),
            ResidualBlock1D(c, 2 * c, stride=2),
            ResidualBlock1D(2 * c, 4 * c, stride=2),
            MeanPool1D(),
        )

    def forward(self, iq: torch.Tensor) -> torch.Tensor:
        return self.network(iq)


class DeployablePhysicalFeatureEncoder(nn.Module):
    """V2 ``PhysicalFeatureEncoder`` with an affine (frozen unit/zero) input norm.

    V2's ``BatchNorm1d(input_channels, affine=False)`` exports its implicit
    scale/bias as ``Constant`` nodes.  An affine BatchNorm frozen at weight=1 and
    bias=0 computes the identical ``(x - mean) / sqrt(var + eps)`` but exports the
    scale/bias as ordinary initializers.  It therefore keeps the eight-operator
    policy while remaining numerically identical to V2 and contributing no
    trainable drift.
    """

    def __init__(self, input_channels: int, base_channels: int = 8) -> None:
        super().__init__()
        c = int(base_channels)
        self.output_features = 4 * c
        input_norm = nn.BatchNorm1d(int(input_channels), affine=True)
        nn.init.ones_(input_norm.weight)
        nn.init.zeros_(input_norm.bias)
        for parameter in input_norm.parameters():
            parameter.requires_grad_(False)
        self.network = nn.Sequential(
            input_norm,
            nn.Conv1d(int(input_channels), c, 5, stride=2, padding=2, bias=False),
            nn.BatchNorm1d(c),
            nn.ReLU(inplace=False),
            ResidualBlock1D(c, 2 * c, stride=2),
            ResidualBlock1D(2 * c, 2 * c, stride=2),
            StatisticalPooling1D(),
        )

    def forward(self, features: torch.Tensor) -> torch.Tensor:
        return self.network(features)


class V2BackboneCore(nn.Module):
    """Deployable V2 backbone: time + physical branches + fusion classifier.

    Its ``state_dict`` keys are exactly V2's ``time_branch.*`` /
    ``physical_branch.*`` / ``classifier.*`` (parameter-bearing indices preserved),
    so a V2 checkpoint loads strictly after synthesizing the affine input-norm
    weight/bias (see :func:`load_v2_into_v3_2`).
    """

    def __init__(
        self,
        num_classes: int,
        *,
        time_base_channels: int = 22,
        physical_base_channels: int = 8,
        fusion_features: int = 64,
        dropout: float = 0.1,
    ) -> None:
        super().__init__()
        self.time_branch = DeployableTimeFeatureExtractor(time_base_channels)
        self.physical_branch = DeployablePhysicalFeatureEncoder(3, physical_base_channels)
        combined = self.time_branch.output_features + self.physical_branch.output_features
        self.classifier = FusionClassifier(combined, fusion_features, num_classes, dropout)

    def forward(self, iq: torch.Tensor, physical_features: torch.Tensor) -> torch.Tensor:
        time_features = self.time_branch(iq)
        physical_embedding = self.physical_branch(physical_features)
        return self.classifier(torch.cat((time_features, physical_embedding), dim=1))


class QAMAwareRFNetV32Core(nn.Module):
    """NPU partition: frozen V2 logits plus a zero-gated QAM delta branch."""

    def __init__(
        self,
        num_classes: int,
        *,
        time_base_channels: int = 22,
        physical_base_channels: int = 8,
        fusion_features: int = 64,
        dropout: float = 0.1,
        delta_hidden: int = 16,
        moment_order: int = 4,
    ) -> None:
        super().__init__()
        self.v2_backbone = V2BackboneCore(
            num_classes,
            time_base_channels=time_base_channels,
            physical_base_channels=physical_base_channels,
            fusion_features=fusion_features,
            dropout=dropout,
        )
        moment_features = 3 * int(moment_order)
        self.delta_pool = HigherOrderMomentPool(moment_order)
        self.delta_norm = nn.BatchNorm1d(moment_features)
        self.delta_head = nn.Sequential(
            nn.Linear(moment_features, int(delta_hidden)),
            nn.ReLU(inplace=False),
            nn.Linear(int(delta_hidden), int(num_classes)),
        )
        self.gate = nn.Parameter(torch.zeros(1))

    def forward(self, iq: torch.Tensor, physical_features: torch.Tensor) -> torch.Tensor:
        v2_logits = self.v2_backbone(iq, physical_features)
        delta = self.delta_head(self.delta_norm(self.delta_pool(physical_features)))
        return v2_logits + self.gate * delta


class QAMAwareRFNetV32(nn.Module):
    """Training graph that computes the frozen physical frontend from IQ.

    ``simulate_hardware_inputs`` defaults to ``False`` so V3.2 trains/evaluates in
    full precision exactly like the frozen V2 champion — the condition that makes
    "initial V3.2 logits == V2 logits" hold end-to-end.  The quantized deployment
    path remains available and unchanged.
    """

    def __init__(self, num_classes: int, **model_config: object) -> None:
        super().__init__()
        self.simulate_hardware_inputs = bool(model_config.pop("simulate_hardware_inputs", False))
        self.physical_frontend = PowerLagOneFeatures()
        self.deployment_emulator = DeploymentInputEmulator()
        self.core = QAMAwareRFNetV32Core(num_classes=num_classes, **model_config)

    def forward(self, iq: torch.Tensor) -> torch.Tensor:
        prepared_iq, physical = self.prepare_inputs(iq)
        return self.core(prepared_iq, physical)

    def prepare_inputs(self, iq: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        if self.simulate_hardware_inputs:
            return self.deployment_emulator(iq)
        return iq, self.physical_frontend(iq)


def build_qam_aware_v3_2(num_classes: int, **model_config: object) -> QAMAwareRFNetV32:
    return QAMAwareRFNetV32(num_classes=num_classes, **model_config)


def build_qam_aware_v3_2_partition(source: QAMAwareRFNetV32) -> QAMAwareRFNetV32Core:
    """Return the exact learned NPU graph; parameters are shared, not copied."""

    return source.core


def load_v2_into_v3_2(model: QAMAwareRFNetV32, checkpoint: dict) -> None:
    """Strictly load the frozen V2 backbone weights into a V3.2 model.

    The V2 ``model_state`` keys map one-to-one onto ``core.v2_backbone.*``.  The
    only keys V2 does not store — the affine weight/bias of the input norm that V2
    defined as ``affine=False`` — are synthesized as ones/zeros (numerically
    identical).  Any other missing or unexpected key is a hard error.
    """

    state = dict(checkpoint["model_state"])
    base = "physical_branch.network.0"
    if f"{base}.weight" not in state:
        channels = int(state[f"{base}.running_mean"].shape[0])
        state[f"{base}.weight"] = torch.ones(channels, dtype=state[f"{base}.running_mean"].dtype)
        state[f"{base}.bias"] = torch.zeros(channels, dtype=state[f"{base}.running_mean"].dtype)
    model.core.v2_backbone.load_state_dict(state, strict=True)


def qam_aware_v3_2_profile(model: nn.Module, sample_length: int = 1024) -> dict[str, float | int | str]:
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
