"""AD-AMR Net — Adaptive Denoising + Efficient Channel Attention AMR network.

Reference: "Adaptive Denoising With Efficient Channel Attention for Automatic
Modulation Recognition", ICC 2024 (`ma.pdf`).

Pipeline (Fig. 1 of the paper):

    noisy IQ x [N, 2, L]
        -> ADM (Adaptive Denoising Module, WaveUNet + ECA)  -> denoised IQ xhat [N, 2, L]
        -> FEM (Feature Extraction Module, stem Conv + stacked ERSBs) -> features [N, C, L']
        -> GAP -> FCL -> softmax logits [N, num_classes]

The network returns ``(logits, denoised_iq)`` so the training loss can combine
cross-entropy with the denoising MSE term (paper Eq. 4: L = alpha * L_MSE + L_CE,
alpha = 0.1).  The paper's ADM takes IQ-only input R^{2 x L}; it does **not** use
the 3-channel physical feature planes of the frozen V2 champion.

Every dimension that the paper leaves unspecified (number of ADM down/up blocks,
channel counts, ECA kernel-size formula, down/up-sampling mechanism, soft-threshold
scaling, FCL hidden size, dropout) is implemented here as an explicit constructor
parameter with a documented default.  See ``docs/implementation_assumptions.md``.
"""

from __future__ import annotations

import io
import math
from typing import Sequence

import torch
import torch.nn.functional as functional
from torch import nn


def eca_kernel_size(channels: int, gamma: float = 2.0, beta: float = 1.0) -> int:
    """Adaptive 1-D ECA kernel size (ECA-Net): k = |log2(C)/gamma + beta/gamma|_odd.

    gamma=2, beta=1 are the ECA-Net paper defaults.  The paper under audit does not
    state gamma/beta; the ECA-Net formula is an implementation assumption.
    """
    k = int(abs(math.log2(max(channels, 2)) / gamma + beta / gamma))
    if k % 2 == 0:
        k += 1
    return max(k, 3)


def soft_threshold(x: torch.Tensor, threshold: torch.Tensor) -> torch.Tensor:
    """Differentiable soft-thresholding (paper Eq. 1) via sign * relu(|x| - lambda)."""
    return torch.sign(x) * torch.relu(torch.abs(x) - threshold)


class ECA(nn.Module):
    """Efficient Channel Attention: GAP -> Conv1d(k) -> Sigmoid -> channel weights.

    ``forward`` returns the per-channel weights ``[N, C, 1]`` (the sigmoid output)
    rather than the scaled input, so the same module can serve two roles:
      * ADM blocks scale features: ``x * eca(x)``;
      * ERSB computes the adaptive threshold scale ``alpha = eca(|out|)``.
    """

    def __init__(self, channels: int, gamma: float = 2.0, beta: float = 1.0) -> None:
        super().__init__()
        kernel = eca_kernel_size(channels, gamma, beta)
        self.conv = nn.Conv1d(1, 1, kernel_size=kernel, padding=kernel // 2, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: [N, C, L] -> weights [N, C, 1]
        gap = x.mean(dim=-1, keepdim=True)          # [N, C, 1]
        gap = gap.squeeze(-1).unsqueeze(1)          # [N, 1, C]
        weights = torch.sigmoid(self.conv(gap))     # [N, 1, C]
        return weights.squeeze(1).unsqueeze(-1)     # [N, C, 1]


class ERSB(nn.Module):
    """Efficient Residual Shrinkage Block (DRSN residual block with SE -> ECA).

    Two convolutions + BN, an identity/projected shortcut, and channel-wise
    adaptive soft-thresholding whose threshold lambda = alpha * mean(|out|) with
    alpha = ECA(|out|) (the efficient-channel-attention replacement of the DRSN
    squeeze-and-excitation threshold generator).
    """

    def __init__(self, in_channels: int, out_channels: int, stride: int = 1,
                 gamma: float = 2.0, beta: float = 1.0) -> None:
        super().__init__()
        self.conv1 = nn.Conv1d(in_channels, out_channels, 3, stride=stride, padding=1, bias=False)
        self.bn1 = nn.BatchNorm1d(out_channels)
        self.conv2 = nn.Conv1d(out_channels, out_channels, 3, stride=1, padding=1, bias=False)
        self.bn2 = nn.BatchNorm1d(out_channels)
        self.eca = ECA(out_channels, gamma, beta)
        self.relu = nn.ReLU(inplace=False)
        if stride == 1 and in_channels == out_channels:
            self.skip = nn.Identity()
        else:
            self.skip = nn.Sequential(
                nn.Conv1d(in_channels, out_channels, 1, stride=stride, bias=False),
                nn.BatchNorm1d(out_channels),
            )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        shortcut = self.skip(x)
        out = self.relu(self.bn1(self.conv1(x)))
        out = self.bn2(self.conv2(out))
        abs_out = torch.abs(out)
        alpha = self.eca(abs_out)                            # [N, C, 1]
        threshold = alpha * abs_out.mean(dim=-1, keepdim=True)
        out = soft_threshold(out, threshold)
        return self.relu(out + shortcut)


class _DownBlock(nn.Module):
    """ADM down-sampling block: Conv1d(k=15, s=2) + BN + ReLU + ECA."""

    def __init__(self, in_channels: int, out_channels: int, kernel: int = 15,
                 gamma: float = 2.0, beta: float = 1.0) -> None:
        super().__init__()
        self.conv = nn.Conv1d(in_channels, out_channels, kernel, stride=2,
                              padding=kernel // 2, bias=False)
        self.bn = nn.BatchNorm1d(out_channels)
        self.eca = ECA(out_channels, gamma, beta)
        self.relu = nn.ReLU(inplace=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.relu(self.bn(self.conv(x)))
        return x * self.eca(x)


class _UpBlock(nn.Module):
    """ADM up-sampling block: nearest x2 upsample + crop-concat skip + Conv1d(k=5) + BN + ReLU + ECA."""

    def __init__(self, in_channels: int, out_channels: int, kernel: int = 5,
                 gamma: float = 2.0, beta: float = 1.0) -> None:
        super().__init__()
        self.conv = nn.Conv1d(in_channels + out_channels, out_channels, kernel, stride=1,
                              padding=kernel // 2, bias=False)
        self.bn = nn.BatchNorm1d(out_channels)
        self.eca = ECA(out_channels, gamma, beta)
        self.relu = nn.ReLU(inplace=False)

    @staticmethod
    def _crop_concat(upsampled: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        # Crop-and-concat skip connection.  For this network's power-of-two lengths
        # (1024/512/256/...) the stride-2 encoder and x2 nearest upsample are exact
        # inverses, so the two lengths always match and the "crop" is the identity;
        # the concat below is the whole operation.  A center-crop branch for odd
        # lengths is intentionally omitted (the ADM requires power-of-two input).
        return torch.cat((upsampled, skip), dim=1)

    def forward(self, x: torch.Tensor, skip: torch.Tensor) -> torch.Tensor:
        x = functional.interpolate(x, scale_factor=2, mode="nearest")
        x = self._crop_concat(x, skip)
        x = self.relu(self.bn(self.conv(x)))
        return x * self.eca(x)


class ADM(nn.Module):
    """Adaptive Denoising Module — WaveUNet-style encoder/decoder with ECA.

    ``num_levels`` down blocks (kernel ``down_kernel``, stride 2) followed by the
    same number of up blocks (nearest x2 upsampling + kernel ``up_kernel`` conv),
    with skip connections (crop-and-concat) and a concluding kernel-1 conv.  The
    module is shape-preserving: [N, 2, L] -> [N, 2, L].
    """

    def __init__(self, in_channels: int = 2, base_channels: int = 16, num_levels: int = 4,
                 down_kernel: int = 15, up_kernel: int = 5,
                 gamma: float = 2.0, beta: float = 1.0) -> None:
        super().__init__()
        if num_levels < 1:
            raise ValueError("num_levels must be >= 1")
        self.num_levels = int(num_levels)
        self.in_channels = int(in_channels)
        self.base_channels = int(base_channels)

        self.encoders = nn.ModuleList()
        ch_in = self.in_channels
        for level in range(self.num_levels):
            ch_out = self.base_channels * (2 ** level)
            self.encoders.append(_DownBlock(ch_in, ch_out, down_kernel, gamma, beta))
            ch_in = ch_out

        self.decoders = nn.ModuleList()
        for level in reversed(range(self.num_levels)):
            ch_in = self.base_channels * (2 ** level)
            ch_out = self.in_channels if level == 0 else self.base_channels * (2 ** (level - 1))
            self.decoders.append(_UpBlock(ch_in, ch_out, up_kernel, gamma, beta))

        self.final = nn.Conv1d(self.in_channels, self.in_channels, 1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        input_x = x
        encoder_outputs: list[torch.Tensor] = []
        for encoder in self.encoders:
            x = encoder(x)
            encoder_outputs.append(x)
        skips = list(reversed(encoder_outputs[:-1]))
        for index, decoder in enumerate(self.decoders):
            skip = input_x if index == len(self.decoders) - 1 else skips[index]
            x = decoder(x, skip)
        return self.final(x)


class FEM(nn.Module):
    """Feature Extraction Module — stem Conv + stacked ERSBs (paper Table I).

    Table I: Conv(k=3,s=1,16) then ERSB(k=3,s=2) with channels 16, 32, 32, 64.
    """

    def __init__(self, in_channels: int = 2, stem_channels: int = 16,
                 ersb_channels: Sequence[int] = (16, 32, 32, 64),
                 strides: Sequence[int] = (2, 2, 2, 2),
                 gamma: float = 2.0, beta: float = 1.0) -> None:
        super().__init__()
        if len(ersb_channels) != len(strides):
            raise ValueError("ersb_channels and strides must have equal length")
        self.output_channels = int(ersb_channels[-1])
        self.stem = nn.Sequential(
            nn.Conv1d(in_channels, stem_channels, 3, stride=1, padding=1, bias=False),
            nn.BatchNorm1d(stem_channels),
            nn.ReLU(inplace=False),
        )
        blocks: list[nn.Module] = []
        ch_in = int(stem_channels)
        for ch_out, stride in zip(ersb_channels, strides):
            blocks.append(ERSB(ch_in, int(ch_out), int(stride), gamma, beta))
            ch_in = int(ch_out)
        self.ersbs = nn.Sequential(*blocks)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.ersbs(self.stem(x))


class ADAMRNet(nn.Module):
    """AD-AMR Net: ADM -> FEM -> GAP -> FCL.

    ``forward`` returns ``(logits, denoised_iq)``.  ``denoised_iq`` feeds the
    denoising MSE term during training only; it never enters the classification
    output that is exported to ONNX.
    """

    def __init__(self, num_classes: int = 8, in_channels: int = 2,
                 adm_base_channels: int = 16, adm_num_levels: int = 4,
                 adm_down_kernel: int = 15, adm_up_kernel: int = 5,
                 eca_gamma: float = 2.0, eca_beta: float = 1.0,
                 fem_stem_channels: int = 16,
                 fem_ersb_channels: Sequence[int] = (16, 32, 32, 64),
                 fem_ersb_strides: Sequence[int] = (2, 2, 2, 2),
                 fusion_features: int = 128, dropout: float = 0.2) -> None:
        super().__init__()
        self.adm = ADM(in_channels, adm_base_channels, adm_num_levels,
                       adm_down_kernel, adm_up_kernel, eca_gamma, eca_beta)
        self.fem = FEM(in_channels, fem_stem_channels, fem_ersb_channels,
                       fem_ersb_strides, eca_gamma, eca_beta)
        self.fc = nn.Sequential(
            nn.Linear(self.fem.output_channels, fusion_features),
            nn.ReLU(inplace=False),
            nn.Dropout(dropout),
            nn.Linear(fusion_features, num_classes),
        )

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        denoised = self.adm(x)
        features = self.fem(denoised)
        features = features.mean(dim=-1)  # global average pooling over time
        logits = self.fc(features)
        return logits, denoised


class ADAMRClassifier(nn.Module):
    """ONNX-friendly wrapper exposing only the classification head (logits)."""

    def __init__(self, model: ADAMRNet) -> None:
        super().__init__()
        self.model = model

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        logits, _ = self.model(x)
        return logits


def build_ad_amr_model(num_classes: int, **model_config: object) -> ADAMRNet:
    allowed = {
        "in_channels", "adm_base_channels", "adm_num_levels", "adm_down_kernel",
        "adm_up_kernel", "eca_gamma", "eca_beta", "fem_stem_channels",
        "fem_ersb_channels", "fem_ersb_strides", "fusion_features", "dropout",
    }
    return ADAMRNet(num_classes=num_classes, **{k: v for k, v in model_config.items() if k in allowed})


def profile_ad_amr_model(model: nn.Module, sample_length: int) -> dict[str, float | int | str]:
    """Report parameter count and neural MAC/FLOP counts (Conv1d + Linear)."""
    parameters = sum(p.numel() for p in model.parameters())
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    macs = 0
    hooks = []

    def count(module: nn.Module, _inputs: tuple, output: torch.Tensor) -> None:
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
        model(torch.zeros(1, 2, sample_length))
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
        "fp32_parameter_size_mb": float(parameters * 4 / (1024 ** 2)),
        "state_dict_size_mb": float(state_bytes / (1024 ** 2)),
        "serialized_state_dict_mb": float(buffer.tell() / (1024 ** 2)),
    }
