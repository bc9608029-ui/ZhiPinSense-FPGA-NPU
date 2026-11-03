"""FFT, spectrum, framing, and energy-detection references."""

from __future__ import annotations

import numpy as np
from scipy import signal


def window_values(length: int, name: str = "hann") -> np.ndarray:
    if name == "rectangular":
        return np.ones(length, dtype=np.float64)
    return signal.get_window(name, length, fftbins=True).astype(np.float64)


def compute_fft(iq: np.ndarray, fft_length: int | None = None, window: str = "hann") -> np.ndarray:
    fft_length = int(fft_length or len(iq))
    segment = np.zeros(fft_length, dtype=np.complex128)
    used = min(len(iq), fft_length)
    segment[:used] = np.asarray(iq)[:used]
    return np.fft.fft(segment * window_values(fft_length, window), n=fft_length)


def power_spectrum(iq: np.ndarray, fft_length: int | None = None, window: str = "hann") -> np.ndarray:
    spectrum = compute_fft(iq, fft_length, window)
    return np.abs(spectrum) ** 2 / len(spectrum)


def frame_signal(iq: np.ndarray, frame_length: int, hop_length: int) -> np.ndarray:
    if frame_length <= 0 or hop_length <= 0:
        raise ValueError("frame_length and hop_length must be positive")
    if len(iq) < frame_length:
        padded = np.pad(iq, (0, frame_length - len(iq)))
        return padded[None, :]
    starts = range(0, len(iq) - frame_length + 1, hop_length)
    return np.stack([iq[start : start + frame_length] for start in starts])


def energy_detect(iq: np.ndarray, frame_length: int, hop_length: int, threshold: float) -> tuple[np.ndarray, np.ndarray]:
    frames = frame_signal(iq, frame_length, hop_length)
    energies = np.mean(np.abs(frames) ** 2, axis=1)
    return energies >= threshold, energies

