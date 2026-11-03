"""Model-level tests: strict V2 load, init equivalence, freeze, profile, contract."""

from __future__ import annotations

from pathlib import Path

import pytest
import torch
import torch.nn.functional as functional

from models.qam_aware_rfnet import build_qam_aware_model
from models.qam_aware_rfnet_v3_3 import (
    build_qam_aware_v3_3,
    freeze_v2_backbone,
    load_v2_into_v3_3,
    qam_aware_v3_3_profile,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
V2_CHECKPOINT = PROJECT_ROOT / "init" / "v2_time_power_phase_best.pt"

FROZEN_V2_TENSORS = 71662  # 71656 V2 params + 6 synthesized affine input-norm params (numel).
EXPERT_A1_TENSORS = 681  # Linear(12,32)=416 + Linear(32,8)=264 + 1 gate (no BatchNorm in the expert).


def _load_v2_checkpoint() -> dict:
    return torch.load(V2_CHECKPOINT, map_location="cpu", weights_only=False)


def _build_teacher(checkpoint: dict) -> torch.nn.Module:
    qam_aware = checkpoint["config"]["qam_aware"]
    teacher = build_qam_aware_model(variant="time_power_phase", num_classes=8, **qam_aware)
    teacher.load_state_dict(checkpoint["model_state"], strict=True)
    teacher.eval()
    return teacher


def _model_config(*, residual_enabled: bool = True, family_enabled: bool = False, **extra: object) -> dict:
    config = {
        "simulate_hardware_inputs": False,
        "time_base_channels": 22,
        "physical_base_channels": 8,
        "fusion_features": 64,
        "dropout": 0.1,
        "residual_expert": {
            "enabled": residual_enabled,
            "moment_order": 4,
            "hidden": 32,
            "gate_init": 0.0,
            "residual_bound": 0.0,
        },
        "family_aux": {"enabled": family_enabled, "hidden": 16},
    }
    config.update(extra)
    return config


def _build_student(checkpoint: dict, *, residual_enabled: bool = True, family_enabled: bool = False) -> torch.nn.Module:
    model = build_qam_aware_v3_3(8, **_model_config(residual_enabled=residual_enabled, family_enabled=family_enabled))
    load_v2_into_v3_3(model, checkpoint)
    model.eval()
    return model


def test_v2_checkpoint_loads_strictly() -> None:
    checkpoint = _load_v2_checkpoint()
    model = build_qam_aware_v3_3(8, **_model_config())
    load_v2_into_v3_3(model, checkpoint)

    v2_keys = set(checkpoint["model_state"].keys())
    backbone_keys = set(model.core.v2_backbone.state_dict().keys())
    assert v2_keys <= backbone_keys, "every V2 key must exist in the V3.3 backbone"
    assert len(backbone_keys - v2_keys) == 2, "only the synthesized affine weight/bias may be extra"

    norm = model.core.v2_backbone.physical_branch.network[0]
    assert torch.all(norm.weight == 1.0)
    assert torch.all(norm.bias == 0.0)
    assert all(parameter.requires_grad is False for parameter in norm.parameters())


def test_a0_output_matches_v2_exactly() -> None:
    checkpoint = _load_v2_checkpoint()
    teacher = _build_teacher(checkpoint)
    student = _build_student(checkpoint, residual_enabled=False)
    assert student.core.expert is None

    torch.manual_seed(0)
    inputs = torch.randn(8, 2, 1024)
    diff = (student(inputs) - teacher(inputs)).abs().max().item()
    assert diff < 1e-6


def test_a1_gate_zero_reproduces_v2() -> None:
    checkpoint = _load_v2_checkpoint()
    teacher = _build_teacher(checkpoint)
    student = _build_student(checkpoint, residual_enabled=True)

    gate = float(student.core.expert.gate.item())
    assert gate == 0.0

    torch.manual_seed(0)
    inputs = torch.randn(8, 2, 1024)
    diff = (student(inputs) - teacher(inputs)).abs().max().item()
    assert diff < 1e-6


def test_frozen_backbone_byte_identical_after_optimizer_step() -> None:
    checkpoint = _load_v2_checkpoint()
    model = _build_student(checkpoint, residual_enabled=True)
    before = {key: value.clone() for key, value in model.core.v2_backbone.state_dict().items()}

    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad], lr=1e-3
    )
    model.train()
    assert model.core.v2_backbone.training is False  # train() override pins eval mode

    torch.manual_seed(0)
    inputs = torch.randn(4, 2, 1024)
    logits, _ = model.forward_with_aux(inputs)
    loss = functional.cross_entropy(logits, torch.randint(0, 8, (4,)))
    optimizer.zero_grad()
    loss.backward()
    optimizer.step()

    after = model.core.v2_backbone.state_dict()
    for key, value in before.items():
        assert torch.equal(value, after[key]), f"frozen backbone key {key!r} drifted"

    for parameter in model.core.v2_backbone.parameters():
        assert parameter.grad is None


def test_only_expert_gets_nonzero_grad() -> None:
    checkpoint = _load_v2_checkpoint()
    model = _build_student(checkpoint, residual_enabled=True)

    torch.manual_seed(0)
    inputs = torch.randn(4, 2, 1024)
    logits, _ = model.forward_with_aux(inputs)
    loss = functional.cross_entropy(logits, torch.randint(0, 8, (4,)))
    loss.backward()

    frozen_with_grad = sum(
        1 for parameter in model.core.v2_backbone.parameters() if parameter.grad is not None
    )
    assert frozen_with_grad == 0
    expert_params = [parameter for parameter in model.core.expert.parameters() if parameter.requires_grad]
    assert all(parameter.grad is not None for parameter in expert_params)
    assert any(parameter.grad.abs().sum().item() > 0 for parameter in expert_params)


def test_freeze_count_and_single_batch_overfit() -> None:
    checkpoint = _load_v2_checkpoint()
    model = _build_student(checkpoint, residual_enabled=True)
    # freeze_v2_backbone returns the number of frozen parameter *tensors* (48),
    # and must touch every one of them, leaving nothing trainable in the backbone.
    frozen = freeze_v2_backbone(model)
    assert frozen == sum(1 for _ in model.core.v2_backbone.parameters())
    assert all(not parameter.requires_grad for parameter in model.core.v2_backbone.parameters())

    optimizer = torch.optim.AdamW(
        [parameter for parameter in model.parameters() if parameter.requires_grad], lr=1e-2
    )
    model.train()
    torch.manual_seed(0)
    inputs = torch.randn(8, 2, 1024)
    labels = torch.randint(0, 8, (8,))

    first_loss = None
    for _ in range(5):
        logits, _ = model.forward_with_aux(inputs)
        loss = functional.cross_entropy(logits, labels)
        if first_loss is None:
            first_loss = loss.item()
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
    assert loss.item() < first_loss, "single-batch optimization must reduce the loss"


def test_logits_are_finite() -> None:
    checkpoint = _load_v2_checkpoint()
    model = _build_student(checkpoint, residual_enabled=True)
    torch.manual_seed(0)
    inputs = torch.randn(8, 2, 1024)
    logits = model(inputs)
    assert torch.isfinite(logits).all()


def test_profile_reports_frozen_and_trainable_counts() -> None:
    checkpoint = _load_v2_checkpoint()
    model = _build_student(checkpoint, residual_enabled=True)
    profile = qam_aware_v3_3_profile(model, 1024)
    assert profile["trainable_parameters"] == EXPERT_A1_TENSORS
    assert profile["frozen_parameters"] == FROZEN_V2_TENSORS
    assert profile["parameters"] == FROZEN_V2_TENSORS + EXPERT_A1_TENSORS


def test_fpga_sim_input_contract_ranges() -> None:
    checkpoint = _load_v2_checkpoint()
    model = _build_student(checkpoint, residual_enabled=True)

    torch.manual_seed(0)
    iq = torch.randn(4, 2, 1024) * 2.0
    prepared_iq, physical = model.deployment_emulator(iq)
    # IQ dequant is SInt8 / 127 -> [-1, 1]; physical is SInt8 * 2/127 -> [-2, 2].
    assert prepared_iq.abs().max().item() <= 1.0 + 1e-6
    assert physical.abs().max().item() <= 2.0 + 1e-6
    assert torch.isfinite(prepared_iq).all()
    assert torch.isfinite(physical).all()
