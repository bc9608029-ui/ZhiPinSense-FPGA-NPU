"""IQ DC removal, RMS normalization, and ADC conversion helpers."""

from __future__ import annotations

import numpy as np


def dc_remove(iq: np.ndarray) -> np.ndarray:
    return np.asarray(iq) - np.mean(iq)


def rms_normalize(iq: np.ndarray, target_rms: float = 1.0, eps: float = 1e-12) -> np.ndarray:
    centered = np.asarray(iq)
    rms = np.sqrt(np.mean(np.abs(centered) ** 2))
    if rms < eps:
        return np.zeros_like(centered)
    return centered * (target_rms / rms)


def complex_to_int16(iq: np.ndarray, full_scale: float = 0.9) -> tuple[np.ndarray, float]:
    """Quantize complex float IQ to interleaved int16 components and return scale."""
    peak = float(max(np.max(np.abs(iq.real)), np.max(np.abs(iq.imag)), 1e-12))
    scale = full_scale * np.iinfo(np.int16).max / peak
    quantized = np.stack((np.round(iq.real * scale), np.round(iq.imag * scale)), axis=-1)
    return np.clip(quantized, -32768, 32767).astype(np.int16), float(scale)


def int16_to_complex(iq_int16: np.ndarray, scale: float) -> np.ndarray:
    array = np.asarray(iq_int16)
    return (array[..., 0].astype(np.float64) + 1j * array[..., 1].astype(np.float64)) / scale

