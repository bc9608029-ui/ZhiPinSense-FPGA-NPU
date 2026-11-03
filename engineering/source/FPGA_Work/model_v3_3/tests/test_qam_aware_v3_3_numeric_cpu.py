"""CPU-runnable numerical-stability test for the V3.3 physical input clamp.

This is the host-equivalent of the release-blocking CUDA gate
(``test_qam_aware_v3_3_full_snr_cuda.py``).  It verifies the deployable input
clamp added in Phase 5 without needing a GPU:

  1. the expert declares the deployment physical-dequant bound ``[-2, 2]``;
  2. deep-negative-SNR (-20 dB) data really does produce |physical| > 2 (the raw
     physical power plane reaches ~10^3, which is why FP16 overflows);
  3. ``prepare_physical`` clamps it back to ``[-2, 2]`` and the order-4 moment
     pool is then finite;
  4. without the clamp the same FP16 moment products overflow (order-2 Inf,
     order-4 NaN) — the exact failure that sank the real RTX 5090 Stage-1;
  5. a full-SNR forward over all 21 SNR points stays finite and the zero-gated
     residual is exactly zero (and thus bounded) at initialization.
"""

from __future__ import annotations

from pathlib import Path

import torch
import torch.nn.functional as functional

from datasets.synthetic_dataset import SyntheticModulationDataset
from models.qam_aware_rfnet_v3_3 import build_qam_aware_v3_3, load_v2_into_v3_3
from training.qam_aware_v3_3_utils import load_qam_aware_v3_3_config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
V2_CHECKPOINT = PROJECT_ROOT / "init" / "v2_time_power_phase_best.pt"

FULL_SNR = [-20, -18, -16, -14, -12, -10, -8, -6, -4, -2, 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20]


def _build(config: dict) -> torch.nn.Module:
    model = build_qam_aware_v3_3(8, **config["model"])
    checkpoint = torch.load(V2_CHECKPOINT, map_location="cpu", weights_only=False)
    load_v2_into_v3_3(model, checkpoint)
    model.eval()
    return model


def _minus20db_iq(config: dict, count: int) -> torch.Tensor:
    dataset = SyntheticModulationDataset(
        count, config["signal"], config["channel"], 2026, "v3_3_train", fixed_snr_db=-20.0
    )
    return torch.stack([dataset[i][0] for i in range(count)])


def test_input_clamp_declares_deploy_contract() -> None:
    config = load_qam_aware_v3_3_config("configs/qam_aware_v3_3.yaml")
    model = _build(config)
    expert = model.core.expert
    assert expert is not None
    assert float(expert.input_clamp_bound) == 2.0
    for name in ("_input_bound", "_input_two_bound", "_neg_one"):
        assert getattr(expert, name) is not None
    assert float(expert._input_bound.item()) == 2.0
    assert float(expert._input_two_bound.item()) == 4.0


def test_minus20db_physical_is_large_and_clamped() -> None:
    config = load_qam_aware_v3_3_config("configs/qam_aware_v3_3.yaml")
    model = _build(config)
    iq = _minus20db_iq(config, 64)
    with torch.no_grad():
        _, physical = model.prepare_inputs(iq)
    assert physical.abs().max().item() > 2.0, "expected -20 dB physical power to exceed the deploy bound"

    clamped = model.core.expert.prepare_physical(physical)
    assert clamped.abs().max().item() <= 2.0 + 1e-4

    moments = model.core.expert.moments(physical)
    assert torch.isfinite(moments).all()


def test_minus20db_fp16_overflow_without_clamp_fixed_with_clamp() -> None:
    config = load_qam_aware_v3_3_config("configs/qam_aware_v3_3.yaml")
    model = _build(config)
    iq = _minus20db_iq(config, 16)
    with torch.no_grad():
        _, physical = model.prepare_inputs(iq)

    # Regression: the *unclamped* FP16 moment products overflow (order-2 Inf,
    # order-4 NaN).  This is the exact failure the input clamp fixes.
    unclamped = model.core.expert.moment_pool(physical.half())
    assert not torch.isfinite(unclamped).all(), "expected FP16 overflow without the clamp"

    # With the clamp, the same FP16 products stay finite and bounded (x^4 <= 16).
    clamped = model.core.expert.prepare_physical(physical.half())
    moments = model.core.expert.moment_pool(clamped)
    assert torch.isfinite(moments).all()
    assert moments.abs().max().item() <= 16.0 + 1e-2


def test_full_snr_forward_finite_and_zero_gate_residual_bounded() -> None:
    config = load_qam_aware_v3_3_config("configs/qam_aware_v3_3.yaml")
    model = _build(config)
    count = len(FULL_SNR) * 8  # one sample per (modulation, SNR) combination
    dataset = SyntheticModulationDataset(
        count, config["signal"], config["channel"], 2026, "v3_3_train", snr_values=FULL_SNR
    )
    iq = torch.stack([dataset[i][0] for i in range(count)])
    labels = torch.tensor([dataset[i][1] for i in range(count)])

    logits, aux = model.forward_with_aux(iq)
    assert torch.isfinite(logits).all()
    loss = functional.cross_entropy(logits, labels)
    assert torch.isfinite(loss).all()

    # gate=0 -> residual is exactly zero, so it is bounded by residual_bound (1.0).
    residual = aux["residual"]
    assert residual.abs().max().item() <= 1.0 + 1e-4
