"""OOD scoring functions on raw logits (pre-softmax).

All five scores follow one convention: **larger value = more OOD**.  Scores are
computed from raw logits only, no softmax probabilities, and are numerically
stabilized against overflow / -inf.

  - MSP        : 1 - max(softmax(logits))
  - MaxLogit   : -max(logits)
  - Entropy    : Shannon entropy of softmax(logits)
  - LogitMargin: -(top1 - top2)                      (negative so larger = more OOD)
  - Energy     : -T * logsumexp(logits / T), T=1.0
"""
from __future__ import annotations

import numpy as np

SCORE_NAMES = ("msp", "max_logit", "entropy", "logit_margin", "energy")


def _logsumexp(logits: np.ndarray, axis: int = -1) -> np.ndarray:
    x = np.asarray(logits, dtype=np.float64)
    m = np.max(x, axis=axis, keepdims=True)
    return m + np.log(np.sum(np.exp(x - m), axis=axis, keepdims=True))


def _softmax(logits: np.ndarray) -> np.ndarray:
    x = np.asarray(logits, dtype=np.float64)
    x = x - np.max(x, axis=-1, keepdims=True)
    e = np.exp(x)
    return e / np.sum(e, axis=-1, keepdims=True)


def score_msp(logits: np.ndarray) -> np.ndarray:
    """1 - max prob; larger = more OOD."""
    probs = _softmax(logits)
    return (1.0 - np.max(probs, axis=-1)).astype(np.float64)


def score_max_logit(logits: np.ndarray) -> np.ndarray:
    """-max logit; larger = more OOD."""
    x = np.asarray(logits, dtype=np.float64)
    return (-np.max(x, axis=-1)).astype(np.float64)


def score_entropy(logits: np.ndarray) -> np.ndarray:
    """Shannon entropy; larger = more OOD."""
    probs = _softmax(logits)
    logp = np.log(np.clip(probs, 1e-12, None))
    return (-np.sum(probs * logp, axis=-1)).astype(np.float64)


def score_logit_margin(logits: np.ndarray) -> np.ndarray:
    """-(top1 - top2); larger = more OOD (small ID margin -> larger score)."""
    x = np.asarray(logits, dtype=np.float64)
    part = np.partition(x, -2, axis=-1)
    top1 = part[..., -1]
    top2 = part[..., -2]
    return (top2 - top1).astype(np.float64)


def score_energy(logits: np.ndarray, temperature: float = 1.0) -> np.ndarray:
    """Free-energy score -T logsumexp(logits/T); larger = more OOD."""
    if temperature <= 0:
        raise ValueError("temperature must be positive")
    x = np.asarray(logits, dtype=np.float64)
    lse = _logsumexp(x / temperature).squeeze(axis=-1)
    return (-temperature * lse).astype(np.float64)


_SCORE_FN = {
    "msp": score_msp,
    "max_logit": score_max_logit,
    "entropy": score_entropy,
    "logit_margin": score_logit_margin,
    "energy": score_energy,
}


def compute_score(logits: np.ndarray, name: str, **kwargs) -> np.ndarray:
    name = str(name).lower()
    if name not in _SCORE_FN:
        raise ValueError(f"unknown OOD score {name!r}; choose from {SCORE_NAMES}")
    return _SCORE_FN[name](logits, **kwargs)


__all__ = [
    "SCORE_NAMES", "score_msp", "score_max_logit", "score_entropy",
    "score_logit_margin", "score_energy", "compute_score",
]
