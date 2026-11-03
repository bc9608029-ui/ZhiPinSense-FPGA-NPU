"""V1.1 Task A — CUDA device/dtype consistency for loss weights.

Offline (CPU) this exercises the defensive cast path so the full CUDA matrix in
``scripts/cuda_preflight.py`` can rely on the same loss code being device-safe.
The assertions run on CPU but check the exact invariant that breaks on CUDA+AMP:
every weight tensor that participates in the loss is on the logits device and in
the logits dtype.
"""

from __future__ import annotations

import torch
import pytest

from contracts.rml24_contract import LABEL_ORDER_24
from v2 import losses as v2_losses


def _logits(dtype: torch.dtype, b: int = 4, c: int = 24) -> torch.Tensor:
    torch.manual_seed(0)
    return torch.randn(b, c, dtype=dtype)


def _targets(b: int = 4, c: int = 24) -> torch.Tensor:
    torch.manual_seed(1)
    return torch.randint(0, c, (b,))


@pytest.mark.parametrize("loss_name", ["label_smoothing", "focal", "class_balanced"])
def test_weight_is_cast_to_logits_dtype(loss_name: str) -> None:
    # Model output in float64, class weight deliberately in float32 -> the loss
    # must cast the weight to the logits dtype/device instead of raising.
    logits = _logits(torch.float64)
    targets = _targets()
    weight = torch.ones(logits.shape[1], dtype=torch.float32)
    fn = getattr(v2_losses, loss_name)
    out = fn(logits, targets, weight=weight) if loss_name != "class_balanced" \
        else fn(logits, targets, class_weights=weight)
    assert torch.isfinite(out)
    assert out.dtype == torch.float64


@pytest.mark.parametrize("loss_name", ["label_smoothing", "focal", "class_balanced"])
def test_loss_without_weight_unchanged(loss_name: str) -> None:
    logits = _logits(torch.float32)
    targets = _targets()
    fn = getattr(v2_losses, loss_name)
    out = fn(logits, targets)
    assert torch.isfinite(out)


def test_trainer_moves_class_weight_to_device() -> None:
    from v2.trainer import V2Trainer

    config = {
        "training": {"learning_rate": 1e-3, "weight_decay": 1e-4, "amp": False,
                     "reconstruction_weight": 0.0},
        "v2": {"class_sampling": "hard_example_16qam_64qam", "loss": "focal",
               "optimizer": "adamw"},
        "model": {},
        "device": "auto",
    }
    trainer = V2Trainer(
        config, {}, list(LABEL_ORDER_24),
        build_model=lambda n, **_: torch.nn.Linear(n, n),
    )
    assert trainer.class_weight is not None
    assert trainer.class_weight.device == trainer.device
    assert trainer.class_weight.dtype == torch.float32


def test_trainer_classification_loss_uses_logits_dtype() -> None:
    from v2.trainer import V2Trainer

    trainer = object.__new__(V2Trainer)
    trainer.class_weight = torch.ones(24, dtype=torch.float32)  # CPU, different dtype
    trainer.loss_name = "focal"
    trainer.focal_gamma = 2.0
    trainer.label_smoothing = 0.1
    trainer.snr_weighting = {}

    logits = _logits(torch.float64)
    labels = _targets()
    snr_db = torch.zeros(4, dtype=torch.float32)
    out = trainer._classification_loss(logits, labels, snr_db)
    assert torch.isfinite(out)


@pytest.mark.parametrize("loss_name", ["cross_entropy", "focal", "label_smoothing",
                                       "class_balanced"])
@pytest.mark.parametrize("optimizer_name", ["adamw", "sgd"])
def test_loss_optimizer_matrix_cpu(loss_name: str, optimizer_name: str) -> None:
    """4 losses x 2 optimizers: forward -> backward -> step, with a class weight
    present so the weight-bearing path is exercised (mirrors the CUDA matrix)."""
    torch.manual_seed(0)
    model = torch.nn.Linear(8, 24)
    weight = torch.ones(24, dtype=torch.float32)
    opt = (torch.optim.AdamW if optimizer_name == "adamw" else torch.optim.SGD)(
        model.parameters(), lr=1e-3,
        **({"momentum": 0.9} if optimizer_name == "sgd" else {}),
    )
    x = torch.randn(4, 8)
    y = torch.randint(0, 24, (4,))
    logits = model(x)

    fn = getattr(v2_losses, loss_name)
    if loss_name == "class_balanced":
        loss = fn(logits, y, class_weights=weight)
    elif loss_name == "label_smoothing":
        loss = fn(logits, y, smoothing=0.1, weight=weight)
    elif loss_name == "focal":
        loss = fn(logits, y, gamma=2.0, weight=weight)
    else:  # cross_entropy ignores weight (**_), exercised for the matrix
        loss = fn(logits, y, weight=weight)

    assert torch.isfinite(loss)
    opt.zero_grad()
    loss.backward()
    assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters())
    opt.step()
