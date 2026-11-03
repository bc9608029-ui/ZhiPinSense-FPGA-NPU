"""Lightweight label-preserving IQ augmentations."""

from __future__ import annotations

import numpy as np


def random_time_shift(iq: np.ndarray, rng: np.random.Generator, max_fraction: float = 0.25) -> np.ndarray:
    max_shift = max(1, int(len(iq) * max_fraction))
    return np.roll(iq, int(rng.integers(-max_shift, max_shift + 1)))


def random_conjugate(iq: np.ndarray, rng: np.random.Generator, probability: float = 0.5) -> np.ndarray:
    return np.conjugate(iq) if rng.random() < probability else iq

