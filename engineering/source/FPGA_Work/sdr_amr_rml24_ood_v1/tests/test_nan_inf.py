"""NaN/Inf handling: metrics stay finite on healthy inputs and NaN propagates so
callers must gate it before writing any PASS."""

from __future__ import annotations

import numpy as np
import torch

from models.rml24_net import build_rml24_model
from ood.energy import energy_score
from ood.metrics import ranking_metrics


def test_metrics_finite_on_separable_random_scores():
    metrics = ranking_metrics(
        np.random.default_rng(0).normal(size=200),
        np.random.default_rng(1).normal(size=200) + 3.0,
    )
    assert all(np.isfinite(value) for value in metrics.values())


def test_model_forward_is_finite():
    model = build_rml24_model(24).eval()
    iq = torch.randn(8, 2, 1024)
    with torch.inference_mode():
        logits, _ = model(iq)
    assert torch.isfinite(logits).all()


def test_nan_logits_propagate_to_nan_score():
    logits = np.array([[np.nan, 0.0, 0.0], [1.0, 2.0, 3.0]])
    result = energy_score(logits)
    assert np.isnan(result[0])
    assert np.isfinite(result[1])
