"""Composable oscillator, converter, and interference impairments."""

from __future__ import annotations

import numpy as np


def carrier_frequency_offset(iq: np.ndarray, offset_hz: float, sample_rate: float) -> np.ndarray:
    n = np.arange(len(iq), dtype=np.float64)
    return (iq * np.exp(1j * 2.0 * np.pi * offset_hz * n / sample_rate)).astype(np.complex64)


def random_phase_offset(iq: np.ndarray, phase_rad: float) -> np.ndarray:
    return (iq * np.exp(1j * phase_rad)).astype(np.complex64)


def phase_noise(iq: np.ndarray, std_rad: float, rng: np.random.Generator) -> np.ndarray:
    phase = np.cumsum(rng.normal(0.0, std_rad, size=len(iq)))
    return (iq * np.exp(1j * phase)).astype(np.complex64)


def sampling_frequency_offset(iq: np.ndarray, ppm: float) -> np.ndarray:
    """Approximate SFO by resampling the record at a linearly drifting time base."""
    original = np.arange(len(iq), dtype=np.float64)
    source_positions = original * (1.0 + ppm * 1e-6)
    source_positions = np.clip(source_positions, 0.0, len(iq) - 1.0)
    real = np.interp(source_positions, original, iq.real)
    imag = np.interp(source_positions, original, iq.imag)
    return (real + 1j * imag).astype(np.complex64)


def iq_imbalance(iq: np.ndarray, gain_db: float, phase_deg: float) -> np.ndarray:
    gain = 10.0 ** (gain_db / 20.0)
    phase = np.deg2rad(phase_deg)
    i = iq.real * gain
    q = iq.imag / gain
    mixed_i = i * np.cos(phase / 2.0) - q * np.sin(phase / 2.0)
    mixed_q = i * np.sin(phase / 2.0) + q * np.cos(phase / 2.0)
    return (mixed_i + 1j * mixed_q).astype(np.complex64)


def add_dc_offset(iq: np.ndarray, magnitude: float, phase_rad: float) -> np.ndarray:
    return (iq + magnitude * np.exp(1j * phase_rad)).astype(np.complex64)


def amplitude_scale(iq: np.ndarray, scale: float) -> np.ndarray:
    return (iq * scale).astype(np.complex64)


def clip_iq(iq: np.ndarray, level_rms: float) -> np.ndarray:
    rms = np.sqrt(np.mean(np.abs(iq) ** 2))
    limit = level_rms * rms
    magnitude = np.abs(iq)
    scale = np.minimum(1.0, limit / np.maximum(magnitude, np.finfo(float).eps))
    return (iq * scale).astype(np.complex64)


def narrowband_interference(
    iq: np.ndarray,
    sample_rate: float,
    sir_db: float,
    frequency_hz: float,
    phase_rad: float,
    reference_power: float | None = None,
) -> np.ndarray:
    signal_power = float(reference_power) if reference_power is not None else float(np.mean(np.abs(iq) ** 2))
    interference_power = signal_power / (10.0 ** (sir_db / 10.0))
    n = np.arange(len(iq), dtype=np.float64)
    tone = np.sqrt(interference_power) * np.exp(1j * (2.0 * np.pi * frequency_hz * n / sample_rate + phase_rad))
    return (iq + tone).astype(np.complex64)


def burst_interference(
    iq: np.ndarray,
    sir_db: float,
    duty_cycle: float,
    rng: np.random.Generator,
    reference_power: float | None = None,
) -> tuple[np.ndarray, tuple[int, int]]:
    length = max(1, int(round(len(iq) * duty_cycle)))
    start = int(rng.integers(0, max(1, len(iq) - length + 1)))
    signal_power = float(reference_power) if reference_power is not None else float(np.mean(np.abs(iq) ** 2))
    burst_power = signal_power / (10.0 ** (sir_db / 10.0))
    noise = rng.normal(size=length) + 1j * rng.normal(size=length)
    noise *= np.sqrt(burst_power / np.mean(np.abs(noise) ** 2))
    result = iq.copy()
    result[start : start + length] += noise
    return result.astype(np.complex64), (start, start + length)
