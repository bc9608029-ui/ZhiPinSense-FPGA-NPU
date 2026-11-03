"""
dsc_amcnet.py
=============
DSC-AMCNet: Depthwise Separable Convolutional AMC Network (4,961 parameters).

Architecture derived from the ULCNN class via systematic ablation and
Pareto width sweep (paper Sections V-VII). Designed for deployment on
ARM Cortex-M7 (STM32H723ZG, 544 MHz) via ST Edge AI Core 2.2.0
(X-CUBE-AI 10.2.0) with signed INT8 post-training quantization.

Input:  (batch, 2, 128)  -- 2-channel (I/Q) 1-D signal, 128 samples,
                            per-window L2-normalized (see normalize_window)
Output: (batch, 11)      -- logits over 11 RML2016.10a modulation classes

Classes (RML2016.10a):
    0: 8PSK   1: AM-DSB   2: AM-SSB   3: BPSK   4: CPFSK
    5: GFSK   6: PAM4     7: QAM16    8: QAM64  9: QPSK
    10: WBFM

Layer-by-layer specification (paper Table V):
    Stem   PWC(2->24, k=1), BN, ReLU                    96 params
    DSC-1  DWC(k=3, g=24), BN, ReLU;
           PWC(24->24), BN, ReLU; MaxPool1d(2)         744 params
    DSC-2  (same structure)                             744 params
    DSC-3  (same structure)                             744 params
    SE     GAP -> FC(24->6), ReLU;
           FC(6->24), Sigmoid; channel scale            318 params
    Shuffle channel shuffle (g=4)                         0 params
    GAP    GlobalAvgPool1d                                0 params
    FC-1   Linear(24->64), ReLU                       1,600 params
    FC-2   Linear(64->11)                               715 params
    Total                                             4,961 params

State-dict key layout matches the released Zenodo checkpoint
(dscamcnet_best.pt): stem.{0,1}, dsc{1,2,3}.{dw,bn1,pw,bn2},
se.{fc1,fc2}, classifier.{0,3}.

Paper: "DSC-AMCNet: Deployment-Guided Automatic Modulation Classification
        on Bare-Metal MCU-Class IoT Devices" (IEEE IoT-J, under review, 2026).
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


def normalize_window(x: torch.Tensor, eps: float = 1e-12) -> torch.Tensor:
    """Per-window L2 normalization used by DSC-AMCNet (paper Section III-C).

    x: (..., 2, 128). The L2 norm is computed over the full 2x128 window.
    """
    flat = x.reshape(*x.shape[:-2], -1)
    norm = flat.norm(p=2, dim=-1, keepdim=True).clamp_min(eps)
    return (flat / norm).reshape_as(x)


class SEBlock(nn.Module):
    """Squeeze-and-Excitation channel attention (r=4 -> 6-unit bottleneck).

    FC layers include bias (paper Table V: SE = 150 + 168 = 318 params).
    """

    def __init__(self, channels: int = 24, reduction: int = 4):
        super().__init__()
        mid = max(1, channels // reduction)
        self.fc1 = nn.Linear(channels, mid, bias=True)
        self.fc2 = nn.Linear(mid, channels, bias=True)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, C, L)
        s = x.mean(dim=2)                # GAP -> (B, C)
        s = F.relu(self.fc1(s))
        s = torch.sigmoid(self.fc2(s))   # (B, C)
        return x * s.unsqueeze(2)


class DSCStage(nn.Module):
    """One depthwise-separable stage: DWC(k=3, g=C) -> BN -> ReLU ->
    PWC(k=1) -> BN -> ReLU -> MaxPool1d(2). All convs bias-free.
    """

    def __init__(self, channels: int = 24, kernel_size: int = 3):
        super().__init__()
        self.dw = nn.Conv1d(channels, channels, kernel_size=kernel_size,
                            padding=kernel_size // 2, groups=channels,
                            bias=False)
        self.bn1 = nn.BatchNorm1d(channels)
        self.pw = nn.Conv1d(channels, channels, kernel_size=1, bias=False)
        self.bn2 = nn.BatchNorm1d(channels)
        self.pool = nn.MaxPool1d(kernel_size=2)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.bn1(self.dw(x)))
        x = F.relu(self.bn2(self.pw(x)))
        return self.pool(x)


def channel_shuffle(x: torch.Tensor, groups: int = 4) -> torch.Tensor:
    """Channel shuffle (g=4): reshape -> transpose -> reshape (0 params)."""
    b, c, l = x.shape
    x = x.reshape(b, groups, c // groups, l)
    x = x.transpose(1, 2).contiguous()
    return x.reshape(b, c, l)


class DSCAMCNet(nn.Module):
    """DSC-AMCNet, 4,961 trainable parameters (paper Table V)."""

    def __init__(self, width: int = 24, num_classes: int = 11,
                 shuffle_groups: int = 4):
        super().__init__()
        self.shuffle_groups = shuffle_groups

        # Stem: PWC(2->24, k=1), BN, ReLU (ReLU applied functionally)
        self.stem = nn.Sequential(
            nn.Conv1d(2, width, kernel_size=1, bias=False),
            nn.BatchNorm1d(width),
        )

        # Three identical DSC stages, each ending in MaxPool1d(2):
        # L: 128 -> 64 -> 32 -> 16
        self.dsc1 = DSCStage(width)
        self.dsc2 = DSCStage(width)
        self.dsc3 = DSCStage(width)

        # SE channel attention on the compressed (B, 24, 16) map
        self.se = SEBlock(width, reduction=4)

        # Classifier: Linear(24->64) -> ReLU -> Identity -> Linear(64->11)
        # (index-3 placement of the final Linear matches the released
        #  checkpoint's key layout: classifier.0.*, classifier.3.*)
        self.classifier = nn.Sequential(
            nn.Linear(width, 64),
            nn.ReLU(inplace=True),
            nn.Identity(),
            nn.Linear(64, num_classes),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = F.relu(self.stem(x))          # (B, 24, 128)
        x = self.dsc1(x)                  # (B, 24, 64)
        x = self.dsc2(x)                  # (B, 24, 32)
        x = self.dsc3(x)                  # (B, 24, 16)
        x = self.se(x)                    # (B, 24, 16)
        x = channel_shuffle(x, self.shuffle_groups)
        x = x.mean(dim=2)                 # GlobalAvgPool1d -> (B, 24)
        return self.classifier(x)         # (B, 11) logits


def build_dsc_amcnet(width: int = 24, num_classes: int = 11) -> DSCAMCNet:
    """Factory matching the paper's deployed configuration."""
    return DSCAMCNet(width=width, num_classes=num_classes)


if __name__ == "__main__":
    model = build_dsc_amcnet()
    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"DSC-AMCNet trainable parameters: {n_params:,} (paper: 4,961)")
    x = torch.randn(1, 2, 128)
    y = model(normalize_window(x))
    print(f"Forward: {tuple(x.shape)} -> {tuple(y.shape)}")
    print("Deployment (paper Table II): 51.26 KB Flash | 12.09 KB RAM | "
          "1.183 ms INT8 @ 544 MHz")
