"""Energy score for OOD detection.

Energy is the free energy ``E(x) = -T * logsumexp(logits / T)``.  For a
well-calibrated classifier, ID inputs concentrate probability mass and have
*lower* (more negative) energy, while OOD inputs spread mass and have *higher*
energy.  We therefore return an anomaly score where higher means more likely OOD.

This must operate on **raw logits** (no softmax), which is exactly what the
ADAMRV11Net and its ONNX export produce.
"""

from __future__ import annotations

import numpy as np


def energy_score(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    """Return the per-sample Energy (anomaly score; higher = more OOD).

    Parameters
    ----------
    logits : np.ndarray, shape ``[N, C]``
        Raw class logits.
    temperature : float
        Temperature scaling ``T > 0``.

    Returns
    -------
    np.ndarray, shape ``[N]``
        ``E(x) = -T * logsumexp(logits / T)``.
    """
    logits = np.asarray(logits, dtype=np.float64)
    if logits.ndim != 2:
        raise ValueError(f"energy_score expects logits of shape [N, C], got {logits.shape}")
    t = float(temperature)
    if t <= 0.0:
        raise ValueError("temperature must be positive")
    scaled = logits / t
    maximum = scaled.max(axis=1, keepdims=True)
    logsumexp = maximum[:, 0] + np.log(np.exp(scaled - maximum).sum(axis=1))
    return -t * logsumexp


def free_energy(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    """Alias of :func:`energy_score` for the standard OOD literature name."""
    return energy_score(logits, temperature)
