"""AD-AMR combined loss: L = L_CE + alpha * L_MSE (paper Eq. 4, alpha = 0.1).

P0 and P1 differ ONLY in the MSE target; the network, initialization, data, seed,
optimizer, learning rate, augmentation and epochs are identical between them.
"""

from __future__ import annotations

import torch
import torch.nn.functional as functional


def ad_amr_loss(
    logits: torch.Tensor,
    denoised_iq: torch.Tensor,
    labels: torch.Tensor,
    clean_iq: torch.Tensor,
    noisy_iq: torch.Tensor,
    variant: str,
    alpha: float,
) -> tuple[torch.Tensor, dict[str, torch.Tensor]]:
    if variant not in ("P0", "P1"):
        raise ValueError(f"unknown loss variant {variant!r}; expected 'P0' or 'P1'")

    ce = functional.cross_entropy(logits, labels)
    target = noisy_iq if variant == "P0" else clean_iq
    mse = functional.mse_loss(denoised_iq, target)
    loss = ce + alpha * mse
    return loss, {"ce": ce, "mse": mse, "loss": loss}
