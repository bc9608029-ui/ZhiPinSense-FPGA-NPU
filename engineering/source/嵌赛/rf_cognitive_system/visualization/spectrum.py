"""FFT spectrum and Welch PSD plotting."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy import signal


def plot_spectrum_and_psd(iq: np.ndarray, sample_rate: float, path: Path, title: str) -> None:
    window = np.hanning(len(iq))
    spectrum = np.fft.fftshift(np.fft.fft(iq * window))
    frequencies = np.fft.fftshift(np.fft.fftfreq(len(iq), d=1.0 / sample_rate)) / 1e3
    magnitude_db = 20.0 * np.log10(np.maximum(np.abs(spectrum), 1e-12))
    magnitude_db -= magnitude_db.max()
    welch_f, psd = signal.welch(iq, fs=sample_rate, nperseg=min(256, len(iq)), return_onesided=False)
    order = np.argsort(welch_f)
    psd_db = 10.0 * np.log10(np.maximum(psd, 1e-15))

    fig, axes = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
    axes[0].plot(frequencies, magnitude_db, label="Windowed FFT")
    axes[0].set(ylabel="Relative magnitude (dB)", title="FFT spectrum")
    axes[0].legend()
    axes[1].plot(welch_f[order] / 1e3, psd_db[order], label="Welch PSD", color="tab:orange")
    axes[1].set(xlabel="Baseband frequency (kHz)", ylabel="PSD (dB/Hz)", title="Power spectral density")
    axes[1].legend()
    for axis in axes:
        axis.grid(True, alpha=0.25)
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)

