"""FIR design and filtering references."""

from __future__ import annotations

import numpy as np
from scipy import signal


def design_lowpass(num_taps: int, cutoff_hz: float, sample_rate: float, window: str = "hamming") -> np.ndarray:
    if not 0.0 < cutoff_hz < sample_rate / 2.0:
        raise ValueError("cutoff_hz must lie between DC and Nyquist")
    return signal.firwin(num_taps, cutoff_hz, fs=sample_rate, window=window).astype(np.float64)


def apply_fir(iq: np.ndarray, taps: np.ndarray) -> np.ndarray:
    return signal.lfilter(np.asarray(taps), [1.0], np.asarray(iq))

