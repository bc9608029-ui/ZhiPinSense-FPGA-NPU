"""Outlier Exposure + Energy loss (M13/M14).

``CE(ID) + lambda * [ relu(E_ID - m_in)^2 + relu(m_out - E_OOD)^2 ]``

The Energy score ``E(x) = -T * logsumexp(logits/T)`` is pulled *below* ``m_in``
for ID and pushed *above* ``m_out`` for OOD, so a single scalar threshold becomes
more separable.  Operates on raw logits (no softmax), which is what the
ADAMRV11Net and its ONNX export produce.
"""

from __future__ import annotations

import torch
import torch.nn.functional as F


def energy_score_t(logits: torch.Tensor, temperature: float = 1.0) -> torch.Tensor:
    """Per-sample Energy ``E(x) = -T * logsumexp(logits/T)`` (lower = more ID)."""
    t = float(temperature)
    if t <= 0.0:
        raise ValueError("temperature must be positive")
    scaled = logits.float() / t
    maximum = scaled.amax(dim=1, keepdim=True)
    logsumexp = (scaled - maximum).exp().sum(dim=1).log() + maximum.squeeze(1)
    return -t * logsumexp


def oe_energy_loss(logits_id: torch.Tensor, labels_id: torch.Tensor,
                   logits_ood: torch.Tensor, *, temperature: float = 1.0,
                   margin_in: float = 0.0, margin_out: float = -10.0,
                   lambda_: float = 0.1) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    """Return ``(total, components)`` where ``components`` holds detached scalars."""
    ce = F.cross_entropy(logits_id, labels_id)
    e_id = energy_score_t(logits_id, temperature)
    e_ood = energy_score_t(logits_ood, temperature)
    pull = F.relu(e_id - float(margin_in)).pow(2).mean()
    push = F.relu(float(margin_out) - e_ood).pow(2).mean()
    oe = pull + push
    total = ce + float(lambda_) * oe
    components = {
        "ce": ce.detach(),
        "energy_pull_id": pull.detach(),
        "energy_push_ood": push.detach(),
    }
    return total, components


__all__ = ["energy_score_t", "oe_energy_loss"]
