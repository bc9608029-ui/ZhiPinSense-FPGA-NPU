"""M5: the 24-class training graph can overfit a single tiny batch.

This is a fast, HDF5-free stand-in for the full ``overfit_probe_rml24`` smoke
gate: it proves the model, CE loss and optimizer are wired so that the loss
collapses and a fixed batch is memorized.  The authoritative gate still runs via
``run_smoke.sh`` against audited RadioML indices.
"""

from __future__ import annotations

import numpy as np
import torch

from models.rml24_net import build_rml24_model
from training.utils import set_seed


def test_single_batch_loss_collapses_and_fits():
    set_seed(3407)
    model = build_rml24_model(24)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    criterion = torch.nn.CrossEntropyLoss()

    n = 24  # one sample per class
    x = torch.randn(n, 2, 1024)
    y = torch.arange(n)

    model.train()
    losses = []
    for _ in range(200):
        optimizer.zero_grad()
        logits, _ = model(x)
        loss = criterion(logits, y)
        loss.backward()
        optimizer.step()
        losses.append(loss.item())

    assert all(np.isfinite(value) for value in losses)
    assert losses[-1] < losses[0] * 0.25

    model.eval()
    with torch.inference_mode():
        logits, _ = model(x)
    accuracy = (logits.argmax(dim=1) == y).float().mean().item()
    assert accuracy >= 0.9
