"""Temperature calibration for raw logits (deterministic, NumPy only).

Temperature scaling is optional; it may improve the separability of Energy, but
the closed-set accuracy (argmax) is temperature-invariant.  The scalar ``T`` is
fit by minimizing the negative log-likelihood on ID validation logits.
"""

from __future__ import annotations

import numpy as np


def _nll(logits: np.ndarray, labels: np.ndarray, inv_temp: float) -> float:
    scaled = logits * inv_temp
    maximum = scaled.max(axis=1, keepdims=True)
    logsumexp = maximum[:, 0] + np.log(np.exp(scaled - maximum).sum(axis=1))
    log_probs = scaled[np.arange(len(labels)), labels] - logsumexp
    return float(-log_probs.mean())


def calibrate_temperature(logits: np.ndarray, labels: np.ndarray,
                          init_temp: float = 1.0, lr: float = 0.05,
                          iters: int = 100, tol: float = 1e-6) -> float:
    """Fit a scalar temperature by NLL gradient descent over ``log(inv_temp)``."""
    logits = np.asarray(logits, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.int64)
    if logits.ndim != 2 or labels.shape[0] != logits.shape[0]:
        raise ValueError("calibrate_temperature expects logits [N, C] and labels [N]")
    if logits.shape[0] < 2:
        return float(init_temp)

    log_inv_temp = float(np.log(1.0 / max(float(init_temp), 1e-9)))
    best = log_inv_temp
    best_nll = _nll(logits, labels, float(np.exp(log_inv_temp)))
    for _ in range(int(iters)):
        current = float(np.exp(log_inv_temp))
        grad = (_nll(logits, labels, current + 1e-4) - _nll(logits, labels, current - 1e-4)) / 2e-4
        log_inv_temp -= lr * grad
        nll = _nll(logits, labels, float(np.exp(log_inv_temp)))
        if nll < best_nll - tol:
            best_nll = nll
            best = log_inv_temp
    temperature = float(1.0 / max(np.exp(best), 1e-9))
    return temperature


def temperature_scale(logits: np.ndarray, temperature: float) -> np.ndarray:
    """Return ``logits / temperature`` (no softmax; raw logits preserved)."""
    t = float(temperature)
    if t <= 0.0:
        raise ValueError("temperature must be positive")
    return np.asarray(logits, dtype=np.float64) / t
