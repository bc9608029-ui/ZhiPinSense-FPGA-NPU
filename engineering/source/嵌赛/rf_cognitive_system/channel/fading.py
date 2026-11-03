"""Flat and frequency-selective fading models."""

from __future__ import annotations

import numpy as np
from scipy import signal


def rayleigh_fading(iq: np.ndarray, rng: np.random.Generator) -> tuple[np.ndarray, dict[str, float]]:
    coefficient = (rng.normal() + 1j * rng.normal()) / np.sqrt(2.0)
    return (iq * coefficient).astype(np.complex64), {
        "coefficient_real": float(coefficient.real),
        "coefficient_imag": float(coefficient.imag),
    }


def rician_fading(iq: np.ndarray, k_factor: float, rng: np.random.Generator) -> tuple[np.ndarray, dict[str, float]]:
    los = np.sqrt(k_factor / (k_factor + 1.0))
    scatter = np.sqrt(1.0 / (k_factor + 1.0)) * (rng.normal() + 1j * rng.normal()) / np.sqrt(2.0)
    coefficient = los + scatter
    return (iq * coefficient).astype(np.complex64), {
        "k_factor": float(k_factor),
        "coefficient_real": float(coefficient.real),
        "coefficient_imag": float(coefficient.imag),
    }


def multipath_fading(
    iq: np.ndarray,
    num_taps: int,
    max_delay: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, dict[str, object]]:
    if num_taps < 1 or max_delay < num_taps - 1:
        raise ValueError("Invalid multipath tap/delay configuration")
    delays = np.sort(rng.choice(np.arange(max_delay + 1), size=num_taps, replace=False))
    delays[0] = 0
    decay = np.exp(-delays / max(max_delay / 3.0, 1.0))
    values = (rng.normal(size=num_taps) + 1j * rng.normal(size=num_taps)) * decay / np.sqrt(2.0)
    values /= np.sqrt(np.sum(np.abs(values) ** 2))
    taps = np.zeros(max_delay + 1, dtype=np.complex128)
    taps[delays] = values
    output = signal.lfilter(taps, [1.0], iq)
    serializable = [[float(value.real), float(value.imag)] for value in values]
    return output.astype(np.complex64), {"delays": delays.tolist(), "tap_values_ri": serializable}

