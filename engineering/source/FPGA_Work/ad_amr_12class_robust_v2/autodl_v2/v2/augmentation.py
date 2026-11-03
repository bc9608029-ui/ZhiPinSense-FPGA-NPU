"""V2 augmentation groups (A/B/C/D) for the robustness ablation.

Design: V1's ``ChannelPipeline`` stays verbatim and is always applied (baseline
domain randomization).  This module adds *new* transforms that V1 does not
implement, applied as a deterministic post-channel stage, plus per-group
*overrides* that extend V1 channel probabilities/ranges.

Every transform here is label-preserving (it never changes the modulation
class), operates on a single complex64 I/Q sample of length ``sample_length``,
and is seeded by a caller-supplied ``np.random.Generator`` so results are
reproducible.

Group taxonomy (documented in docs/AUGMENTATION_ABLATION.md):
  A  geometry / timing      (phase, time shift, IQ swap, conjugate, amplitude, SRO)
  B  channel                (fading, delay spread, frequency-selective fading)
  C  hardware / receiver    (nonlinear PA, ADC quantization, analog frontend)
  D  interference           (adjacent-channel, partial-band, narrowband/burst)
"""

from __future__ import annotations

import numpy as np

GROUP_NAMES = ("A", "B", "C", "D")


def time_shift(iq: np.ndarray, rng: np.random.Generator, max_shift: int = 0) -> np.ndarray:
    """Cyclic time shift (samples stay aligned; frame content rotates)."""
    if max_shift <= 0:
        return iq
    shift = int(rng.integers(-max_shift, max_shift + 1))
    if shift == 0:
        return iq
    return np.roll(iq, shift)


def iq_swap(iq: np.ndarray, rng: np.random.Generator | None = None) -> np.ndarray:
    """Swap I and Q (receiver quadrature wiring)."""
    return iq.imag + 1j * iq.real


def conjugate(iq: np.ndarray, rng: np.random.Generator | None = None) -> np.ndarray:
    """Complex conjugation (LO sign / spectrum mirror)."""
    return np.conj(iq)


def frequency_selective_fading(iq: np.ndarray, rng: np.random.Generator,
                               n_taps: int = 5, max_gain_db: float = 6.0) -> np.ndarray:
    """Apply a short random frequency-selective filter in the time domain.

    Uses a real FIR with random taps, normalized to unit power, then equalizes
    to keep RMS ~ 1.0 so downstream AGC assumptions still hold.
    """
    taps = rng.normal(0.0, 1.0, size=max(1, n_taps)).astype(np.float64)
    taps *= 10.0 ** (rng.uniform(-max_gain_db, max_gain_db) / 20.0)
    taps /= np.sqrt(np.sum(taps ** 2))
    out = np.convolve(iq.astype(np.complex128), taps, mode="same")
    out = _renorm(out)
    return out.astype(np.complex64)


def nonlinear_pa(iq: np.ndarray, rng: np.random.Generator, input_backoff_db: float = 6.0,
                 knee: float = 2.0) -> np.ndarray:
    """Memoryless soft AM/AM nonlinearity (Rapp-style) on the amplitude."""
    x = iq.astype(np.complex128)
    scale = 10.0 ** (-input_backoff_db / 20.0)
    x = x * scale
    r = np.abs(x)
    out = x / (1.0 + (r / knee) ** 2) ** 0.25  # soft saturation
    out = _renorm(out)
    return out.astype(np.complex64)


def quantize(iq: np.ndarray, rng: np.random.Generator | None = None, bits: int = 16) -> np.ndarray:
    """Uniform mid-rise ADC quantization to ``bits`` (fixed-point effect)."""
    bits = int(bits)
    if bits >= 24:
        return iq
    levels = 2 ** bits
    peak = np.max(np.abs(iq)) if iq.size else 1.0
    peak = max(peak, 1e-6)
    norm = np.clip(iq / peak, -1.0, 1.0)
    q = np.round((norm + 1.0) / 2.0 * (levels - 1)) / (levels - 1) * 2.0 - 1.0
    return (q * peak).astype(np.complex64)


def analog_filter(iq: np.ndarray, rng: np.random.Generator | None = None,
                  fs: float = 128000.0, cutoff_hz: float = 0.0) -> np.ndarray:
    """Low-pass frontend rolloff (FIR, Hamming window, linear phase)."""
    if cutoff_hz <= 0.0 or cutoff_hz >= fs / 2.0:
        return iq
    n = 65
    fc = cutoff_hz / fs
    idx = np.arange(n)
    taps = np.sinc(2.0 * fc * (idx - (n - 1) / 2.0)) * (2.0 * fc)
    taps *= np.hamming(n)
    taps /= taps.sum()
    out = np.convolve(iq.astype(np.complex128), taps, mode="same")
    return _renorm(out).astype(np.complex64)


def adjacent_channel(iq: np.ndarray, rng: np.random.Generator, fs: float = 128000.0,
                     offset_hz: float = 0.0, sir_db: float = 10.0) -> np.ndarray:
    """Add a bandlimited interferer offset from the signal's carrier."""
    if offset_hz <= 0.0:
        return iq
    n = iq.size
    t = np.arange(n, dtype=np.float64) / fs
    # Interferer: bandlimited (low-passed) white noise shifted in frequency.
    interferer = rng.normal(0.0, 1.0, size=n) + 1j * rng.normal(0.0, 1.0, size=n)
    interferer = analog_filter(interferer.astype(np.complex64), None, fs=fs, cutoff_hz=fs / 8.0).astype(np.complex128)
    interferer *= np.exp(2j * np.pi * offset_hz * t)
    interferer *= 10.0 ** (-sir_db / 20.0)
    return _renorm(iq.astype(np.complex128) + interferer).astype(np.complex64)


def partial_band_interference(iq: np.ndarray, rng: np.random.Generator,
                              fraction: float = 0.0, sir_db: float = 6.0) -> np.ndarray:
    """Add noise to a contiguous fraction of the (cyclic) band."""
    fraction = float(np.clip(fraction, 0.0, 1.0))
    if fraction <= 0.0:
        return iq
    n = iq.size
    spectrum = np.fft.fft(iq.astype(np.complex128))
    noise = np.fft.fft(rng.normal(0.0, 1.0, size=n) + 1j * rng.normal(0.0, 1.0, size=n))
    width = max(1, int(round(n * fraction)))
    start = int(rng.integers(0, n))
    mask = np.zeros(n, dtype=np.float64)
    idx = (np.arange(width) + start) % n
    mask[idx] = 10.0 ** (-sir_db / 20.0)
    out = np.fft.ifft(spectrum + mask * noise)
    return _renorm(out).astype(np.complex64)


def _renorm(x: np.ndarray) -> np.ndarray:
    rms = np.sqrt(np.mean(np.abs(x) ** 2))
    if rms < 1e-9:
        return x
    return x / rms


# Group specs.  Each group lists:
#   channel_overrides — V1 ChannelPipeline probability/range extensions
#                       (merged into the baseline channel config);
#   transforms        — new post-channel transforms as
#                       (name, probability, default_kwargs).
GROUP_SPECS: dict[str, dict] = {
    "A": {
        "channel_overrides": {
            "phase_offset": {"probability": 0.9},
            "amplitude_scaling": {"probability": 0.9, "scale": [0.6, 1.6]},
            "sfo": {"probability": 0.3, "ppm": [-120.0, 120.0]},
        },
        "transforms": [
            ("time_shift", 0.5, {"max_shift": 128}),
            ("iq_swap", 0.2, {}),
            ("conjugate", 0.2, {}),
        ],
    },
    "B": {
        "channel_overrides": {
            "multipath": {"probability": 0.5, "taps": [2, 6], "max_delay": 24},
            "rayleigh": {"probability": 0.25},
            "rician": {"probability": 0.25, "k": [2.0, 12.0]},
        },
        "transforms": [
            ("frequency_selective_fading", 0.5, {"n_taps": 5, "max_gain_db": 6.0}),
        ],
    },
    "C": {
        "channel_overrides": {
            "iq_imbalance": {"probability": 0.3, "gain_db": [-1.5, 1.5], "phase_deg": [-8.0, 8.0]},
            "clipping": {"probability": 0.15, "level_rms": [1.4, 2.2]},
            "dc_offset": {"probability": 0.15, "mag": [0.0, 0.08]},
        },
        "transforms": [
            ("nonlinear_pa", 0.4, {"input_backoff_db": 6.0, "knee": 2.0}),
            ("quantize", 0.5, {"bits": 8}),
            ("analog_filter", 0.5, {"fs": 128000.0, "cutoff_hz": 56000.0}),
        ],
    },
    "D": {
        "channel_overrides": {
            "narrowband": {"probability": 0.4, "strength_db": [-15.0, -5.0]},
            "burst": {"probability": 0.2, "duration_ratio": [0.1, 0.6]},
        },
        "transforms": [
            ("adjacent_channel", 0.5, {"fs": 128000.0, "offset_hz": 32000.0, "sir_db": 10.0}),
            ("partial_band_interference", 0.5, {"fraction": 0.25, "sir_db": 6.0}),
        ],
    },
}

_TRANSFORM_FN = {
    "time_shift": time_shift,
    "iq_swap": iq_swap,
    "conjugate": conjugate,
    "frequency_selective_fading": frequency_selective_fading,
    "nonlinear_pa": nonlinear_pa,
    "quantize": quantize,
    "analog_filter": analog_filter,
    "adjacent_channel": adjacent_channel,
    "partial_band_interference": partial_band_interference,
}


class V2Augmentor:
    """Deterministic post-channel augmentation stage for a set of groups."""

    def __init__(self, groups: list[str] | tuple[str, ...] | None = None):
        if groups is None:
            groups = ["A", "B", "C", "D"]
        self.groups: list[str] = []
        self.transforms: list[tuple[str, float, dict]] = []
        for name in groups:
            if name not in GROUP_SPECS:
                raise ValueError(f"unknown augmentation group {name!r}")
            self.groups.append(name)
            self.transforms.extend(GROUP_SPECS[name]["transforms"])

    @staticmethod
    def channel_overrides(groups: list[str] | tuple[str, ...]) -> dict:
        merged: dict = {}
        for name in groups:
            if name not in GROUP_SPECS:
                raise ValueError(f"unknown augmentation group {name!r}")
            for key, value in GROUP_SPECS[name]["channel_overrides"].items():
                merged[key] = dict(value)
        return merged

    def __call__(self, iq: np.ndarray, rng: np.random.Generator) -> np.ndarray:
        out = np.asarray(iq, dtype=np.complex64).copy()
        for name, probability, kwargs in self.transforms:
            if probability <= 0.0:
                continue
            if probability >= 1.0 or rng.random() < probability:
                out = _TRANSFORM_FN[name](out, rng, **kwargs)
        return out
