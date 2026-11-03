"""Bit-exact reference for the post-FFT PL stream writer."""

from __future__ import annotations

import numpy as np


FFT_LENGTH = 1024
POWER_MAX = (1 << 54) - 1


def natural_to_shifted_address(index: np.ndarray | int):
    return np.asarray(index) ^ (FFT_LENGTH // 2)


def power_u54(real: np.ndarray, imag: np.ndarray) -> np.ndarray:
    real = np.asarray(real, dtype=np.int64)
    imag = np.asarray(imag, dtype=np.int64)
    power = real * real + imag * imag
    if np.any(power < 0) or np.any(power > POWER_MAX):
        raise ValueError("FFT magnitude exceeds frozen unsigned-54-bit contract")
    return power.astype(np.int64)


def write_frame_natural(real: np.ndarray, imag: np.ndarray) -> np.ndarray:
    if len(real) != FFT_LENGTH or len(imag) != FFT_LENGTH:
        raise ValueError("exactly 1024 natural-order FFT bins are required")
    output = np.empty(FFT_LENGTH, dtype=np.int64)
    addresses = natural_to_shifted_address(np.arange(FFT_LENGTH))
    output[addresses] = power_u54(real, imag)
    return output
