"""V2 classification losses for Phase B (no teacher distillation).

Phase B candidates (documented in docs/V2_ACCEPTANCE_GATES.md):
  cross_entropy      — baseline CE (+ optional reconstruction);
  label_smoothing    — CE with uniform label smoothing;
  focal              — focal loss (down-weight easy samples);
  class_balanced     — inverse-frequency class weights on CE.

All losses take ``(logits, targets)`` plus optional per-loss kwargs and return
a scalar ``torch.Tensor``.  Reconstruction is added by the trainer, not here.
"""

from __future__ import annotations

from typing import Any

import torch
import torch.nn.functional as F


def cross_entropy(logits: torch.Tensor, targets: torch.Tensor, **_: Any) -> torch.Tensor:
    return F.cross_entropy(logits, targets)


def label_smoothing(logits: torch.Tensor, targets: torch.Tensor,
                    smoothing: float = 0.1, weight: torch.Tensor | None = None,
                    **_: Any) -> torch.Tensor:
    return F.cross_entropy(logits, targets, label_smoothing=float(smoothing), weight=weight)


def focal(logits: torch.Tensor, targets: torch.Tensor, gamma: float = 2.0,
          weight: torch.Tensor | None = None, **_: Any) -> torch.Tensor:
    ce = F.cross_entropy(logits, targets, reduction="none", weight=weight)
    prob = torch.exp(-ce)
    factor = (1.0 - prob) ** float(gamma)
    return (factor * ce).mean()


def class_balanced(logits: torch.Tensor, targets: torch.Tensor,
                   class_weights: torch.Tensor | None = None, **_: Any) -> torch.Tensor:
    if class_weights is None:
        return F.cross_entropy(logits, targets)
    return F.cross_entropy(logits, targets, weight=class_weights.to(logits.device))


_LOSS_FN = {
    "cross_entropy": cross_entropy,
    "label_smoothing": label_smoothing,
    "focal": focal,
    "class_balanced": class_balanced,
}


def compute_class_weights(targets: torch.Tensor, num_classes: int,
                          eps: float = 1e-6) -> torch.Tensor:
    """Inverse-frequency class weights from a target tensor."""
    counts = torch.bincount(targets.long(), minlength=num_classes).float()
    counts = counts.clamp_min(1.0)  # avoid div-by-zero for missing classes
    weights = (1.0 / (counts + eps))
    weights = weights / weights.sum() * num_classes
    return weights


def build_loss(name: str, **kwargs: Any):
    if name not in _LOSS_FN:
        raise ValueError(f"unknown v2 loss {name!r}")
    return lambda logits, targets: _LOSS_FN[name](logits, targets, **kwargs)
