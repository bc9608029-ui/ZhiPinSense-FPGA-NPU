"""Board-independent golden reference for wideband signal discovery."""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
from scipy import signal


@dataclass(frozen=True)
class DiscoveryConfig:
    fft_length: int = 1024
    hop_length: int = 512
    threshold_db: float = 9.0
    merge_gap_bins: int = 2
    min_region_bins: int = 2

    def __post_init__(self) -> None:
        if self.fft_length < 2:
            raise ValueError("fft_length must be at least 2")
        if not 1 <= self.hop_length <= self.fft_length:
            raise ValueError("hop_length must be in [1, fft_length]")
        if not np.isfinite(self.threshold_db):
            raise ValueError("threshold_db must be finite")
        if self.merge_gap_bins < 0:
            raise ValueError("merge_gap_bins must be non-negative")
        if self.min_region_bins < 1:
            raise ValueError("min_region_bins must be positive")


@dataclass(frozen=True)
class DetectedSignal:
    first_bin: int
    last_bin: int
    center_frequency_hz: float
    occupied_bandwidth_hz: float
    integrated_power: float
    estimated_snr_db: float


def average_power_spectrum(
    iq: np.ndarray, sample_rate: float, config: DiscoveryConfig
) -> tuple[np.ndarray, np.ndarray]:
    """Hann-windowed, overlap-averaged FFT power in shifted frequency order."""

    values = np.asarray(iq, dtype=np.complex128)
    if not np.isfinite(sample_rate) or sample_rate <= 0.0:
        raise ValueError("sample_rate must be finite and positive")
    if values.ndim != 1 or len(values) < config.fft_length:
        raise ValueError("IQ must be one-dimensional and contain at least one FFT frame")
    if not np.all(np.isfinite(values)):
        raise ValueError("IQ must contain only finite samples")
    starts = np.arange(0, len(values) - config.fft_length + 1, config.hop_length)
    window = np.hanning(config.fft_length)
    window_energy = float(np.sum(window * window))
    spectra = []
    for start in starts:
        transformed = np.fft.fftshift(np.fft.fft(values[start : start + config.fft_length] * window))
        spectra.append(np.abs(transformed) ** 2 / window_energy)
    power = np.mean(np.stack(spectra), axis=0)
    frequencies = np.fft.fftshift(np.fft.fftfreq(config.fft_length, d=1.0 / sample_rate))
    return frequencies, power


def estimate_noise_floor(power: np.ndarray) -> float:
    """Robust scalar noise estimate from the lower 75% of spectrum bins."""

    values = np.asarray(power, dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("Power must be a finite non-empty one-dimensional array")
    if np.any(values < 0.0):
        raise ValueError("Power cannot be negative")
    cutoff = np.quantile(values, 0.75)
    retained = values[values <= cutoff]
    return float(np.median(retained) / np.log(2.0))


def merge_detected_bins(mask: np.ndarray, max_gap: int, min_region_bins: int) -> list[tuple[int, int]]:
    values = np.asarray(mask, dtype=bool)
    if values.ndim != 1:
        raise ValueError("Detection mask must be one-dimensional")
    if max_gap < 0 or min_region_bins < 1:
        raise ValueError("max_gap must be non-negative and min_region_bins positive")
    indices = np.flatnonzero(values)
    if len(indices) == 0:
        return []
    regions: list[tuple[int, int]] = []
    first = previous = int(indices[0])
    for raw_index in indices[1:]:
        index = int(raw_index)
        if index - previous - 1 > max_gap:
            if previous - first + 1 >= min_region_bins:
                regions.append((first, previous))
            first = index
        previous = index
    if previous - first + 1 >= min_region_bins:
        regions.append((first, previous))
    return regions


def discover_signals(
    iq: np.ndarray, sample_rate: float, config: DiscoveryConfig = DiscoveryConfig()
) -> dict[str, object]:
    """Detect, merge and estimate signal regions in a wideband IQ record."""

    frequencies, power = average_power_spectrum(iq, sample_rate, config)
    noise_floor = estimate_noise_floor(power)
    threshold = noise_floor * 10.0 ** (config.threshold_db / 10.0)
    regions = merge_detected_bins(power > threshold, config.merge_gap_bins, config.min_region_bins)
    bin_width = float(sample_rate / config.fft_length)
    detections: list[DetectedSignal] = []
    for first, last in regions:
        region_power = power[first : last + 1]
        weights = np.maximum(region_power - noise_floor, 0.0)
        weight_sum = float(np.sum(weights))
        if weight_sum <= 0.0:
            continue
        center = float(np.sum(frequencies[first : last + 1] * weights) / weight_sum)
        signal_power = float(np.sum(weights))
        noise_power = max(noise_floor * len(region_power), np.finfo(float).tiny)
        detections.append(
            DetectedSignal(
                first_bin=first,
                last_bin=last,
                center_frequency_hz=center,
                occupied_bandwidth_hz=(last - first + 1) * bin_width,
                integrated_power=signal_power,
                estimated_snr_db=float(10.0 * np.log10(signal_power / noise_power)),
            )
        )
    return {
        "config": asdict(config),
        "sample_rate_hz": float(sample_rate),
        "analysis_record_length": int(len(np.asarray(iq))),
        "window": "symmetric Hann (numpy.hanning)",
        "spectrum_units": "relative power per FFT bin; not calibrated W/Hz",
        "bin_width_hz": bin_width,
        "noise_floor": noise_floor,
        "threshold": threshold,
        "frequencies_hz": frequencies,
        "power_spectrum": power,
        "detections": [asdict(item) for item in detections],
    }


def extract_signal_frame(
    iq: np.ndarray,
    sample_rate: float,
    center_frequency_hz: float,
    occupied_bandwidth_hz: float,
    target_sample_rate: float = 128_000.0,
    target_length: int = 1024,
    fir_taps: int = 129,
) -> tuple[np.ndarray, dict[str, float | int]]:
    """Golden DDC, low-pass and rational resampling into an AMR frame."""

    values = np.asarray(iq, dtype=np.complex128)
    if values.ndim != 1 or values.size == 0 or not np.all(np.isfinite(values)):
        raise ValueError("IQ must be a finite non-empty one-dimensional record")
    if not np.isfinite(sample_rate) or sample_rate <= 0.0:
        raise ValueError("sample_rate must be finite and positive")
    if not np.isfinite(target_sample_rate) or target_sample_rate <= 0.0:
        raise ValueError("target_sample_rate must be finite and positive")
    if target_length < 1:
        raise ValueError("target_length must be positive")
    if fir_taps < 3 or fir_taps % 2 == 0:
        raise ValueError("fir_taps must be an odd integer of at least 3")
    if not np.isfinite(center_frequency_hz) or abs(center_frequency_hz) >= sample_rate / 2.0:
        raise ValueError("center_frequency_hz must lie strictly inside the Nyquist interval")
    if occupied_bandwidth_hz <= 0.0 or occupied_bandwidth_hz >= sample_rate:
        raise ValueError("occupied_bandwidth_hz must be in (0, sample_rate)")
    sample_indices = np.arange(len(values), dtype=np.float64)
    shifted = values * np.exp(-1j * 2.0 * np.pi * center_frequency_hz * sample_indices / sample_rate)
    cutoff = min(0.65 * occupied_bandwidth_hz, 0.45 * sample_rate)
    taps = signal.firwin(fir_taps, cutoff=cutoff, fs=sample_rate)
    filtered = signal.lfilter(taps, [1.0], shifted)
    delay = (fir_taps - 1) // 2
    filtered = filtered[delay:]
    up = int(round(target_sample_rate))
    down = int(round(sample_rate))
    divisor = int(np.gcd(up, down))
    resample_up = up // divisor
    resample_down = down // divisor
    resampled = signal.resample_poly(filtered, resample_up, resample_down)
    if len(resampled) < target_length:
        result = np.pad(resampled, (0, target_length - len(resampled)))
    else:
        result = resampled[:target_length]
    return result.astype(np.complex64), {
        "input_sample_rate_hz": float(sample_rate),
        "target_sample_rate_hz": float(target_sample_rate),
        "center_frequency_hz": float(center_frequency_hz),
        "occupied_bandwidth_hz": float(occupied_bandwidth_hz),
        "filter_cutoff_hz": float(cutoff),
        "fir_taps": int(fir_taps),
        "filter_group_delay_input_samples": int(delay),
        "resample_up": int(resample_up),
        "resample_down": int(resample_down),
        "input_length": int(len(values)),
        "output_length": int(target_length),
    }
