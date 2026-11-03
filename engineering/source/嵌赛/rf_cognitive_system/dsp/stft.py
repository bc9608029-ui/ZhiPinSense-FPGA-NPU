"""Short-time Fourier transform reference."""

from __future__ import annotations

import numpy as np
from scipy import signal


def compute_stft(
    iq: np.ndarray,
    sample_rate: float,
    nperseg: int = 128,
    noverlap: int = 64,
    window: str = "hann",
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    frequencies, times, spectrum = signal.stft(
        iq,
        fs=sample_rate,
        window=window,
        nperseg=nperseg,
        noverlap=noverlap,
        return_onesided=False,
        boundary=None,
    )
    return np.fft.fftshift(frequencies), times, np.fft.fftshift(spectrum, axes=0)

