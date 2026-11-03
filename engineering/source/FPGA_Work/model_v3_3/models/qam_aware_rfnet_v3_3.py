"""QAM-Aware RFNet V3.3 — truly-frozen V2 backbone + bounded residual expert.

V3.3 learns from the V3.1/V3.2 gate failures.  The two prior tracks both kept
the V2 champion's backbone effectively trainable (V3.2 froze only the 6 affine
input-norm parameters, leaving 72025/72031 parameters trainable and letting the
backbone drift by 9%-42% per seed).  V3.3 closes that hole by construction:

* the deployable V2 ``TimePowerPhaseRFNet`` backbone is loaded **strictly** from
  the frozen champion and every one of its parameters is frozen with
  ``requires_grad_(False)`` — no last-block gradual unfreeze is enabled by
  default, and the freeze is re-verified from the real checkpoint;
* a small, separate **zero-gated** residual expert can only *additively* correct
  the V2 logits:

      logits = v2_logits + gate * delta,     gate = 0 at initialization.

  The expert is a higher-order-moment branch on the three physical planes
  (power, lag1_real, lag1_imag) — the one V3.1/V3.2 result that genuinely
  helped the 16QAM/64QAM amplitude-ring boundary.  It is bounded in magnitude
  by the zero gate initialization, a residual L2 penalty and (optionally) a
  deployable hard clamp expressed only with Add/Mul/Relu.

* A0/A1/A2/A3 are one model class selected by configuration, never stacked:

  * ``A0`` — ``residual_expert.enabled = false``: the frozen V2 baseline with
    real train/validation metrics (the "V2 can win" fallback);
  * ``A1`` — frozen V2 + zero-gated bounded residual expert;
  * ``A2`` — A1 + a train-only family auxiliary head (PSK/QAM/FSK/OFDM);
  * ``A3`` — A2 + a train-only numeric-domain consistency loss between the
    full-precision path and the FPGA Mandatory-Core emulated path.

Only the ``core`` (frozen V2 backbone + residual expert) is exported to ONNX.
The physical frontend, family head, and domain-consistency machinery are
training/evaluation-only and never enter the deployed NPU graph.
"""

from __future__ import annotations

import io
from typing import Any

import torch
from torch import nn

from models.dual_domain_rfnet import FusionClassifier, ResidualBlock1D
from models.qam_aware_rfnet import PowerLagOneFeatures, StatisticalPooling1D

FAMILY_NAMES = ["PSK", "QAM", "FSK", "OFDM"]
# Class order is the frozen deployment contract:
#   BPSK, QPSK, 8PSK, 16QAM, 64QAM, 2FSK, CPFSK, OFDM
FAMILY_ID_OF_CLASS = [0, 0, 0, 1, 1, 2, 2, 3]


class MeanPool1D(nn.Module):
    """Global temporal mean replacing ``AdaptiveAvgPool1d(1)`` + ``Flatten``.

    A plain ``mean(dim=-1)`` produces the identical ``[N, C]`` result but
    exports as ``ReduceMean``, which is inside the frozen NPU operator policy.
    It has no parameters, so the V2 ``state_dict`` keys are unchanged.
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

    V2's ``BatchNorm1d(..., affine=False)`` exports its implicit scale/bias as
    ``Constant`` nodes.  An affine BatchNorm frozen at weight=1 and bias=0
    computes the identical ``(x - mean) / sqrt(var + eps)`` but exports the
    scale/bias as ordinary initializers.  It therefore keeps the eight-operator
    NPU policy while remaining numerically identical to V2 and contributing no
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
    ``physical_branch.*`` / ``classifier.*`` (parameter-bearing indices
    preserved), so a V2 checkpoint loads strictly after synthesizing the affine
    input-norm weight/bias (see :func:`load_v2_into_v3_3`).
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


class HigherOrderMomentPool(nn.Module):
    """Concatenate ``E[x], E[x^2], ..., E[x^order]`` for every feature channel.

    Implemented only with element-wise multiplication and a temporal mean, so it
    compiles to Mul/ReduceMean/Concat on the ZG330 NPU.  ``order=2`` reproduces
    ``StatisticalPooling1D`` exactly.
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


class BoundedResidualExpert(nn.Module):
    """Zero-gated residual expert on higher-order moments of the physical planes.

    ``gate`` starts at exactly zero, so ``v2_logits + gate * delta == v2_logits``
    element-wise at initialization (max_abs_diff = 0).  The residual magnitude is
    bounded three ways: the zero gate, an optional deployable hard clamp on the
    *final residual* ``gate * delta`` (Add/Mul/Relu only, so
    ``|logits - v2_logits| <= residual_bound`` for every input), and the residual
    L2 penalty the trainer adds.  Clamping only ``delta`` would leave the product
    ``gate * delta`` unbounded because ``gate`` is itself trainable.

    The expert input (the physical planes) is clamped to
    ``[-input_clamp_bound, input_clamp_bound]`` before the moment pool.  This
    matches the FPGA/NPU physical dequant contract (``int8 * 2/127`` -> ``[-2, 2]``)
    and keeps the order-4 moment products finite in FP16 for deep-negative-SNR
    samples whose physical power otherwise reaches ~10^3 (see ``prepare_physical``).

    ``forward`` returns only logits (the deployable path); ``forward_with_feat``
    additionally returns the post-ReLU hidden representation consumed by the
    family auxiliary head.
    """

    def __init__(
        self,
        num_classes: int,
        *,
        moment_order: int = 4,
        hidden: int = 32,
        gate_init: float = 0.0,
        residual_bound: float = 0.0,
        input_clamp_bound: float = 2.0,
        input_channels: int = 3,
    ) -> None:
        super().__init__()
        self.moment_order = int(moment_order)
        moment_features = int(input_channels) * self.moment_order
        self.moment_pool = HigherOrderMomentPool(self.moment_order)
        # Deliberately no BatchNorm here.  The physical planes are already O(1)
        # in both the full-precision and FPGA-emulated numeric domains, and an
        # eval-mode BatchNorm exports as a ``BatchNormalization`` node that some
        # torch versions then decorate with ``Identity`` aliases outside the
        # eight-operator policy.  The following Linear layer learns the scale.
        self.mlp = nn.Sequential(
            nn.Linear(moment_features, int(hidden)),
            nn.ReLU(inplace=False),
            nn.Linear(int(hidden), int(num_classes)),
        )
        self.gate = nn.Parameter(torch.full((1,), float(gate_init)))
        self.residual_bound = float(residual_bound)
        # Deployable input clamp: the FPGA/NPU physical dequant contract is
        # int8 * (2/127) -> [-2, 2], so the expert must never see |physical| > 2.
        # Without it, -20 dB samples (physical power ~975) overflow FP16 in the
        # order-2/order-4 moment products (Inf/NaN); after the clamp x^4 <= 16.
        self.input_clamp_bound = float(input_clamp_bound)
        if self.residual_bound > 0.0:
            bound = float(residual_bound)
            self.register_buffer("_clamp_bound", torch.tensor(bound))
            self.register_buffer("_two_bound", torch.tensor(2.0 * bound))
        if self.input_clamp_bound > 0.0:
            # 1-element *1-D* buffers, deliberately NOT 0-dim scalars: the residual
            # clamp's ``_two_bound`` is a 0-dim ``2.0``, and a 0-dim ``_input_bound``
            # of the same value would be folded into it by the JIT constant-pooling
            # pass and re-materialized by the ONNX exporter as an ``Identity`` node
            # outside the eight-operator policy.  The distinct shape keeps the two
            # clamps' bounds as separate initializers (Add/Mul/Relu only).
            ibound = float(input_clamp_bound)
            self.register_buffer("_input_bound", torch.tensor([ibound]))
            self.register_buffer("_input_two_bound", torch.tensor([2.0 * ibound]))
        if self.residual_bound > 0.0 or self.input_clamp_bound > 0.0:
            self.register_buffer("_neg_one", torch.tensor(-1.0))

    def _clamp_to(
        self, value: torch.Tensor, b: torch.Tensor, two_b: torch.Tensor, neg: torch.Tensor
    ) -> torch.Tensor:
        """Hard clamp to ``[-b, b]`` with only Add/Mul/Relu (see ``_clamp``)."""
        lower = torch.relu(value + b)
        return b + neg * torch.relu(two_b + neg * lower)

    def _clamp(self, value: torch.Tensor) -> torch.Tensor:
        """Hard clamp to ``[-residual_bound, residual_bound]`` with only Add/Mul/Relu.

        ``clamp(x, -b, b) = b + (-1) * relu((2b) + (-1) * relu(x + b))``.
        The bounds and the ``-1`` are registered buffers, so the ONNX exporter
        materialises them as initializers.  ``2b`` is a dedicated buffer (not
        ``b + b``) so no ``constant + constant`` sub-expression exists for the
        exporter to fold into a ``Constant``/``Clip``/``Sub`` node — every
        operator stays inside the eight-operator NPU policy.
        """

        return self._clamp_to(value, self._clamp_bound, self._two_bound, self._neg_one)

    def prepare_physical(self, physical_features: torch.Tensor) -> torch.Tensor:
        """Clamp the physical planes to ``[-input_clamp_bound, input_clamp_bound]``.

        Aligns the expert input with the FPGA/NPU physical dequant contract
        (``int8 * 2/127`` -> ``[-2, 2]``) and keeps the order-4 moment products
        finite in FP16.  Uses only Add/Mul/Relu over registered buffers, so the
        exported graph stays inside the eight-operator NPU policy.
        """

        if self.input_clamp_bound > 0.0:
            return self._clamp_to(
                physical_features, self._input_bound, self._input_two_bound, self._neg_one
            )
        return physical_features

    def moments(self, physical_features: torch.Tensor) -> torch.Tensor:
        """Higher-order moments of the *clamped* physical planes (for diagnostics)."""
        return self.moment_pool(self.prepare_physical(physical_features))

    def _delta(self, physical_features: torch.Tensor) -> torch.Tensor:
        moments = self.moments(physical_features)
        return self.mlp(moments)

    def _residual(self, delta: torch.Tensor) -> torch.Tensor:
        """Clamp the *final* residual ``gate * delta`` (not ``delta`` alone).

        ``gate`` is a trainable scalar, so clamping only ``delta`` leaves the
        product ``gate * delta`` unbounded.  The hard clamp is applied to the
        actual logit correction so ``|logits - v2_logits| <= residual_bound``
        holds for every input no matter how large ``gate`` or the expert weights
        grow.  The clamp is expressed only with Add/Mul/Relu (see ``_clamp``).
        """

        residual = self.gate * delta
        if self.residual_bound > 0.0:
            residual = self._clamp(residual)
        return residual

    def forward(self, v2_logits: torch.Tensor, physical_features: torch.Tensor) -> torch.Tensor:
        return v2_logits + self._residual(self._delta(physical_features))

    def forward_with_feat(
        self, v2_logits: torch.Tensor, physical_features: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        moments = self.moments(physical_features)
        hidden = self.mlp[1](self.mlp[0](moments))
        delta = self.mlp[2](hidden)
        residual = self._residual(delta)
        return v2_logits + residual, hidden, residual


class QAMAwareRFNetV33Core(nn.Module):
    """Deployable NPU graph: frozen V2 logits plus a bounded residual expert.

    Takes ``(iq, physical_features)`` and returns ``logits``.  This is the exact
    graph exported to ONNX; the family head is deliberately absent from
    ``forward`` so it can never leak into the deployed partition.
    """

    def __init__(
        self,
        num_classes: int,
        *,
        time_base_channels: int = 22,
        physical_base_channels: int = 8,
        fusion_features: int = 64,
        dropout: float = 0.1,
        residual_expert: dict[str, Any] | None = None,
        family_aux: dict[str, Any] | None = None,
    ) -> None:
        super().__init__()
        self.v2_backbone = V2BackboneCore(
            num_classes,
            time_base_channels=time_base_channels,
            physical_base_channels=physical_base_channels,
            fusion_features=fusion_features,
            dropout=dropout,
        )
        residual_config = dict(residual_expert or {})
        self.residual_enabled = bool(residual_config.pop("enabled", True))
        if self.residual_enabled:
            self.expert = BoundedResidualExpert(num_classes, **residual_config)
        else:
            self.expert = None
        family_config = dict(family_aux or {})
        self.family_enabled = bool(family_config.pop("enabled", False))
        self.family_head: nn.Module | None = None
        if self.family_enabled:
            hidden = int(family_config.pop("hidden", 16))
            self.family_head = nn.Sequential(
                nn.Linear(int(residual_config.get("hidden", 32)), hidden),
                nn.ReLU(inplace=False),
                nn.Linear(hidden, len(FAMILY_NAMES)),
            )

    def forward(self, iq: torch.Tensor, physical_features: torch.Tensor) -> torch.Tensor:
        v2_logits = self.v2_backbone(iq, physical_features)
        if self.expert is None:
            return v2_logits
        return self.expert(v2_logits, physical_features)

    def forward_with_aux(
        self, iq: torch.Tensor, physical_features: torch.Tensor
    ) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        v2_logits = self.v2_backbone(iq, physical_features)
        aux: dict[str, torch.Tensor] = {}
        if self.expert is None:
            logits = v2_logits
            aux["residual"] = torch.zeros_like(v2_logits)
        else:
            logits, hidden, residual = self.expert.forward_with_feat(v2_logits, physical_features)
            aux["residual"] = residual
            if self.family_head is not None:
                aux["family"] = self.family_head(hidden)
        return logits, aux


class QAMAwareRFNetV33(nn.Module):
    """Training graph that computes the physical frontend from IQ.

    ``simulate_hardware_inputs`` defaults to ``False`` so V3.3 trains/evaluates
    in full precision exactly like the frozen V2 champion — the condition that
    makes "initial V3.3 logits == V2 logits" hold end-to-end.  The quantized
    deployment path remains available and unchanged for the A3 domain-consistency
    loss and the FPGA bit-exact tests.
    """

    def __init__(self, num_classes: int, **model_config: Any) -> None:
        super().__init__()
        self.simulate_hardware_inputs = bool(model_config.pop("simulate_hardware_inputs", False))
        self.physical_frontend = PowerLagOneFeatures()
        self.deployment_emulator = DeploymentInputEmulator()
        self.core = QAMAwareRFNetV33Core(num_classes=num_classes, **model_config)

    def forward(self, iq: torch.Tensor) -> torch.Tensor:
        prepared_iq, physical = self.prepare_inputs(iq)
        return self.core(prepared_iq, physical)

    def train(self, mode: bool = True) -> "QAMAwareRFNetV33":
        super().train(mode)
        # The frozen V2 backbone must stay in eval mode even while the expert
        # trains, so its BatchNorm running stats and dropout remain frozen.
        self.core.v2_backbone.eval()
        return self

    def prepare_inputs(self, iq: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        if self.simulate_hardware_inputs:
            return self.deployment_emulator(iq)
        return iq, self.physical_frontend(iq)

    def forward_with_aux(self, iq: torch.Tensor) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
        prepared_iq, physical = self.prepare_inputs(iq)
        return self.core.forward_with_aux(prepared_iq, physical)

    def forward_domain(self, iq: torch.Tensor, *, hardware_sim: bool) -> torch.Tensor:
        if hardware_sim:
            prepared_iq, physical = self.deployment_emulator(iq)
        else:
            prepared_iq, physical = iq, self.physical_frontend(iq)
        return self.core(prepared_iq, physical)


def _round_nearest_away_from_zero(value: torch.Tensor) -> torch.Tensor:
    return torch.where(value >= 0, torch.floor(value + 0.5), torch.ceil(value - 0.5))


class DeploymentInputEmulator(nn.Module):
    """Emulate the frozen Q15 -> FPGA INT8 -> host FP32 input contract.

    Training/evaluation-only; excluded from :class:`QAMAwareRFNetV33Core` because
    real hardware supplies these already-quantized planes to the compiled NPU
    graph.  Mirror of the Mandatory-Core reference (``hardware.fpga.python``).
    """

    def __init__(self) -> None:
        super().__init__()
        self.physical_frontend = PowerLagOneFeatures()

    def forward(self, iq: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        q15_counts = _round_nearest_away_from_zero(
            torch.clamp(iq, min=-1.0, max=32767.0 / 32768.0) * 32768.0
        )
        q15 = q15_counts / 32768.0
        iq_int8 = torch.clamp(_round_nearest_away_from_zero(q15_counts * (127.0 / 32768.0)), -127, 127)
        iq_dequantized = iq_int8 / 127.0

        physical_q30 = self.physical_frontend(q15)
        physical_int8 = torch.clamp(
            _round_nearest_away_from_zero(physical_q30 * (127.0 / 2.0)), -127, 127
        )
        physical_dequantized = physical_int8 * (2.0 / 127.0)
        return iq_dequantized, physical_dequantized


def build_qam_aware_v3_3(num_classes: int, **model_config: Any) -> QAMAwareRFNetV33:
    return QAMAwareRFNetV33(num_classes=num_classes, **model_config)


def build_qam_aware_v3_3_partition(source: QAMAwareRFNetV33) -> QAMAwareRFNetV33Core:
    """Return the exact learned NPU graph; parameters are shared, not copied."""

    return source.core


def load_v2_into_v3_3(model: QAMAwareRFNetV33, checkpoint: dict[str, Any]) -> None:
    """Strictly load and **freeze** the frozen V2 backbone into a V3.3 model.

    The V2 ``model_state`` keys map one-to-one onto ``core.v2_backbone.*``.  The
    only keys V2 does not store — the affine weight/bias of the input norm that
    V2 defined as ``affine=False`` — are synthesized as ones/zeros (numerically
    identical).  Any other missing or unexpected key is a hard error.  After the
    load, every ``v2_backbone`` parameter is frozen with ``requires_grad_(False)``.
    """

    state = dict(checkpoint["model_state"])
    base = "physical_branch.network.0"
    if f"{base}.weight" not in state:
        channels = int(state[f"{base}.running_mean"].shape[0])
        state[f"{base}.weight"] = torch.ones(channels, dtype=state[f"{base}.running_mean"].dtype)
        state[f"{base}.bias"] = torch.zeros(channels, dtype=state[f"{base}.running_mean"].dtype)
    model.core.v2_backbone.load_state_dict(state, strict=True)
    freeze_v2_backbone(model)


def freeze_v2_backbone(model: QAMAwareRFNetV33) -> int:
    """Freeze every V2 backbone parameter and pin its BatchNorm running stats.

    Returns the number of frozen parameter tensors.  In addition to
    ``requires_grad_(False)`` on every parameter, the backbone is put into eval
    mode so its BatchNorm layers keep the champion's running statistics (instead
    of re-accumulating them over V3.3 batches) and its dropout stays off.  A
    ``train()`` override on the wrapper re-applies this pin after every
    ``model.train()`` call, so the frozen backbone can never drift — the hole
    that sank V3.2.
    """

    count = 0
    for parameter in model.core.v2_backbone.parameters():
        parameter.requires_grad_(False)
        count += 1
    model.core.v2_backbone.eval()
    return count


def v3_3_family_ids(num_classes: int) -> torch.Tensor:
    """Class-index -> family-index mapping used by the train-only family head."""

    if num_classes != len(FAMILY_ID_OF_CLASS):
        raise ValueError("V3.3 family mapping is defined for the frozen 8-class order")
    return torch.tensor(FAMILY_ID_OF_CLASS, dtype=torch.long)


def qam_aware_v3_3_profile(model: nn.Module, sample_length: int = 1024) -> dict[str, float | int | str]:
    """Profile learned work without counting the fixed FPGA frontend."""

    parameters = sum(parameter.numel() for parameter in model.parameters())
    trainable = sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
    frozen = sum(
        parameter.numel() for parameter in model.parameters() if not parameter.requires_grad
    )
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
        x = next(model.parameters())
        model(x.new_zeros((1, 2, int(sample_length))))
    model.train(was_training)
    for hook in hooks:
        hook.remove()

    state_bytes = sum(tensor.numel() * tensor.element_size() for tensor in model.state_dict().values())
    buffer = io.BytesIO()
    torch.save(model.state_dict(), buffer)
    return {
        "parameters": int(parameters),
        "trainable_parameters": int(trainable),
        "frozen_parameters": int(frozen),
        "neural_macs": int(macs),
        "neural_flops": int(2 * macs),
        "fp32_parameter_size_mb": float(parameters * 4 / (1024**2)),
        "checkpoint_tensor_state_size_mb": float(state_bytes / (1024**2)),
        "serialized_state_dict_mb": float(buffer.tell() / (1024**2)),
        "input_contract": "iq[N,2,1024] + physical[N,3,1024] -> logits[N,8]",
        "operator_policy": "Conv/BatchNorm/ReLU/Add/Concat/ReduceMean/Mul/Gemm only",
    }
