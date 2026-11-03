"""Additive white Gaussian noise with measured-SNR metadata."""

from __future__ import annotations

import numpy as np


def measure_snr_db(clean: np.ndarray, noisy: np.ndarray) -> float:
    noise = noisy - clean
    signal_power = float(np.mean(np.abs(clean) ** 2))
    noise_power = float(np.mean(np.abs(noise) ** 2))
    return 10.0 * np.log10(signal_power / max(noise_power, np.finfo(float).tiny))


def add_awgn(
    iq: np.ndarray,
    snr_db: float,
    rng: np.random.Generator | None = None,
    exact_power: bool = True,
    reference_power: float | None = None,
) -> tuple[np.ndarray, dict[str, float]]:
    """Add complex AWGN relative to desired-signal power.

    ``iq`` may already contain interference. In that case ``reference_power``
    must be the desired component power so SNR and SIR remain independent.
    """
    rng = rng or np.random.default_rng()
    signal_power = float(reference_power) if reference_power is not None else float(np.mean(np.abs(iq) ** 2))
    target_noise_power = signal_power / (10.0 ** (snr_db / 10.0))
    noise = rng.normal(size=iq.shape) + 1j * rng.normal(size=iq.shape)
    if exact_power:
        noise *= np.sqrt(target_noise_power / np.mean(np.abs(noise) ** 2))
    else:
        noise *= np.sqrt(target_noise_power / 2.0)
    output = iq + noise
    actual_noise_power = float(np.mean(np.abs(noise) ** 2))
    measured = 10.0 * np.log10(signal_power / actual_noise_power)
    return output.astype(np.complex64), {
        "target_snr_db": float(snr_db),
        "measured_snr_db": float(measured),
        "signal_power": signal_power,
        "noise_power": actual_noise_power,
    }
