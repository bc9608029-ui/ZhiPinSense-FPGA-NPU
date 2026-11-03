"""Synthetic OOD generator for the 24-class OE framework (M25-B, self-contained).

Produces deterministic near/far OOD IQ families as RMS=1 planar ``[N, 2, 1024]``
float32 arrays, using ``numpy.random.SeedSequence([seed, split_code, family_code])``
for a three-way isolation of oe_aux_train / ood_validation / ood_final_test.

OOD samples are NOT a 25th class: they are auxiliary inputs shaped by the Energy
OE loss and scored by the OOD metrics, never merged into the 24 ID labels.  Every
waveform here is a reasonable synthetic approximation, not a standard-exact
transmitter, exactly as the v1.1 framework documents.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import signal

# Near OOD for the 24-class model: modulations in the 12-class set but not the 24.
OOD_NEAR_24 = ("2FSK", "GFSK", "OFDM")

# Ambiguous near-equivalents (excluded from the main OOD metrics).
OOD_AMBIGUOUS = ("AM-DSB", "WBFM")

# Far OOD (shared by both models).
OOD_FAR = ("LFM", "CW", "MULTITONE", "PULSE", "FHOP")

# Stable per-modulation family codes (distinct streams under SeedSequence).
FAMILY_CODE = {
    "2FSK": 0, "GFSK": 1, "OFDM": 2, "AM-DSB": 3, "WBFM": 4,
    "LFM": 5, "CW": 6, "MULTITONE": 7, "PULSE": 8, "FHOP": 9,
}

SPLIT_CODE = {"oe_aux_train": 0, "ood_validation": 1, "ood_final_test": 2}


@dataclass(frozen=True)
class SignalConfig:
    sample_rate: float = 200_000.0
    sample_length: int = 1024
    amplitude: float = 1.0
    samples_per_symbol: int = 8
    span_symbols: int = 6
    rolloff: float = 0.35
    frequency_offset: float = 0.0
    phase_offset: float = 0.0


def root_raised_cosine_taps(samples_per_symbol: int, span_symbols: int,
                            beta: float) -> np.ndarray:
    """Normalized root-raised-cosine filter taps."""
    n = samples_per_symbol * span_symbols
    t = (np.arange(n) - (n - 1) / 2.0) / samples_per_symbol
    taps = np.zeros(n, dtype=np.float64)
    for i, ti in enumerate(t):
        if abs(ti) < 1e-9:
            taps[i] = 1.0 - beta + 4.0 * beta / np.pi
        elif abs(abs(ti) - 1.0 / (4.0 * beta)) < 1e-9:
            taps[i] = (beta / np.sqrt(2.0)) * (
                (1.0 + 2.0 / np.pi) * np.sin(np.pi / (4.0 * beta))
                + (1.0 - 2.0 / np.pi) * np.cos(np.pi / (4.0 * beta))
            )
        else:
            taps[i] = (
                np.sin(np.pi * ti * (1.0 - beta))
                + 4.0 * beta * ti * np.cos(np.pi * ti * (1.0 + beta))
            ) / (np.pi * ti * (1.0 - (4.0 * beta * ti) ** 2))
    taps /= np.sqrt(np.sum(taps ** 2))
    return taps


def _normalize_rms(iq: np.ndarray, amplitude: float) -> np.ndarray:
    iq = np.asarray(iq, dtype=np.complex128)
    rms = float(np.sqrt(np.mean(np.abs(iq) ** 2)))
    if rms <= 1e-12:
        raise ValueError("generated OOD waveform has zero power")
    return iq * (amplitude / rms)


def _apply_rotation(iq: np.ndarray, cfg: SignalConfig) -> np.ndarray:
    n = cfg.sample_length
    rotation = np.exp(1j * (2.0 * np.pi * cfg.frequency_offset * np.arange(n) / cfg.sample_rate
                            + cfg.phase_offset))
    return (iq * rotation)[:n]


def _shape(symbols: np.ndarray, cfg: SignalConfig) -> np.ndarray:
    taps = root_raised_cosine_taps(cfg.samples_per_symbol, cfg.span_symbols, cfg.rolloff)
    shaped = signal.upfirdn(taps, symbols, up=cfg.samples_per_symbol)
    delay = (len(taps) - 1) // 2
    start = delay + cfg.span_symbols * cfg.samples_per_symbol
    out = shaped[start:start + cfg.sample_length]
    if len(out) < cfg.sample_length:
        out = np.pad(out, (0, cfg.sample_length - len(out)))
    return out[:cfg.sample_length].astype(np.complex128)


def _bandlimited_message(rng: np.random.Generator, cfg: SignalConfig,
                         bandwidth_hz: float) -> np.ndarray:
    guard = 256
    white = rng.standard_normal(cfg.sample_length + 2 * guard)
    taps = signal.firwin(129, bandwidth_hz, fs=cfg.sample_rate, window="hann")
    msg = signal.lfilter(taps, [1.0], white)[guard:guard + cfg.sample_length]
    msg -= float(np.mean(msg))
    peak = float(np.max(np.abs(msg)))
    if peak <= 1e-12:
        raise ValueError("generated analog message has zero amplitude")
    return msg / peak


def _generate_2fsk(rng: np.random.Generator, cfg: SignalConfig) -> np.ndarray:
    sps = cfg.samples_per_symbol
    nsym = int(np.ceil(cfg.sample_length / sps)) + 4
    syms = 2.0 * rng.integers(0, 2, size=nsym) - 1.0
    nrz = np.repeat(syms, sps)
    deviation = 0.25 * cfg.sample_rate / sps
    phase = 2.0 * np.pi * np.cumsum(nrz * deviation) / cfg.sample_rate
    return np.exp(1j * (phase + rng.uniform(-np.pi, np.pi)))[:cfg.sample_length]


def _generate_gfsk(rng: np.random.Generator, cfg: SignalConfig) -> np.ndarray:
    sps = cfg.samples_per_symbol
    nsym = int(np.ceil(cfg.sample_length / sps)) + 4
    syms = 2.0 * rng.integers(0, 2, size=nsym) - 1.0
    nrz = np.repeat(syms, sps)
    span = 4
    n_taps = 2 * span * sps + 1
    sigma = max(sps / (2.0 * np.pi * 0.3), 1.0)
    g = signal.windows.gaussian(n_taps, std=sigma)
    g /= np.sum(g)
    shaped = signal.fftconvolve(nrz, g, mode="same")
    deviation = 0.25 * cfg.sample_rate / sps
    phase = 2.0 * np.pi * np.cumsum(shaped * deviation) / cfg.sample_rate
    return np.exp(1j * (phase + rng.uniform(-np.pi, np.pi)))[:cfg.sample_length]


def _generate_ofdm(rng: np.random.Generator, cfg: SignalConfig) -> np.ndarray:
    n = cfg.sample_length
    n_sub = 16
    symbols = np.exp(1j * 2.0 * np.pi * rng.integers(0, 4, size=n_sub) / 4.0)
    freqs = (np.arange(n_sub) - n_sub / 2.0) * (cfg.sample_rate / n)
    iq = np.zeros(n, dtype=np.complex128)
    for k, f in enumerate(freqs):
        iq += symbols[k] * np.exp(1j * 2.0 * np.pi * f * np.arange(n) / cfg.sample_rate)
    return iq


def _generate_am_dsb(rng: np.random.Generator, cfg: SignalConfig) -> np.ndarray:
    bandwidth = float(rng.uniform(2500.0, 7000.0))
    index = float(rng.uniform(0.35, 0.9))
    message = _bandlimited_message(rng, cfg, bandwidth)
    carrier = np.exp(1j * rng.uniform(-np.pi, np.pi)) * np.ones(cfg.sample_length)
    return carrier * (1.0 + index * message)


def _generate_wbfm(rng: np.random.Generator, cfg: SignalConfig) -> np.ndarray:
    bandwidth = float(rng.uniform(4000.0, 12000.0))
    deviation = float(rng.uniform(12000.0, 30000.0))
    message = _bandlimited_message(rng, cfg, bandwidth)
    phase = 2.0 * np.pi * deviation * np.cumsum(message) / cfg.sample_rate
    return np.exp(1j * (phase + rng.uniform(-np.pi, np.pi)))


def _generate_lfm(rng: np.random.Generator, cfg: SignalConfig) -> np.ndarray:
    n = cfg.sample_length
    t = np.arange(n, dtype=np.float64) / cfg.sample_rate
    f0 = float(rng.uniform(-0.3, 0.1) * cfg.sample_rate)
    f1 = float(rng.uniform(0.1, 0.3) * cfg.sample_rate)
    k = (f1 - f0) / (n / cfg.sample_rate)
    phase = 2.0 * np.pi * (f0 * t + 0.5 * k * t ** 2) + rng.uniform(-np.pi, np.pi)
    return np.exp(1j * phase)


def _generate_cw(rng: np.random.Generator, cfg: SignalConfig) -> np.ndarray:
    n = np.arange(cfg.sample_length, dtype=np.float64)
    f0 = float(rng.uniform(-0.4, 0.4) * cfg.sample_rate)
    return np.exp(1j * (2.0 * np.pi * f0 * n / cfg.sample_rate + rng.uniform(-np.pi, np.pi)))


def _generate_multitone(rng: np.random.Generator, cfg: SignalConfig) -> np.ndarray:
    n = np.arange(cfg.sample_length, dtype=np.float64)
    count = int(rng.integers(3, 8))
    iq = np.zeros(cfg.sample_length, dtype=np.complex128)
    for _ in range(count):
        f = float(rng.uniform(-0.4, 0.4) * cfg.sample_rate)
        phase = float(rng.uniform(-np.pi, np.pi))
        amp = float(rng.uniform(0.3, 1.0))
        iq += amp * np.exp(1j * (2.0 * np.pi * f * n / cfg.sample_rate + phase))
    return iq


def _generate_pulse(rng: np.random.Generator, cfg: SignalConfig) -> np.ndarray:
    n = cfg.sample_length
    period = int(rng.integers(32, 128))
    duty = float(rng.uniform(0.1, 0.5))
    on = (np.arange(n) % period) < int(duty * period)
    f0 = float(rng.uniform(-0.3, 0.3) * cfg.sample_rate)
    carrier = np.exp(1j * 2.0 * np.pi * f0 * np.arange(n) / cfg.sample_rate)
    return (on * carrier).astype(np.complex128)


def _generate_fhop(rng: np.random.Generator, cfg: SignalConfig) -> np.ndarray:
    n = cfg.sample_length
    hop_len = int(rng.integers(64, 256))
    n_hops = int(np.ceil(n / hop_len)) + 1
    freqs = rng.uniform(-0.4, 0.4, size=n_hops) * cfg.sample_rate
    phase = 0.0
    segments: list[np.ndarray] = []
    idx = 0
    for h in range(n_hops):
        length = min(hop_len, n - idx)
        if length <= 0:
            break
        nn = np.arange(length, dtype=np.float64)
        segments.append(np.exp(1j * (2.0 * np.pi * freqs[h] * nn / cfg.sample_rate + phase)))
        phase += 2.0 * np.pi * freqs[h] * length / cfg.sample_rate
        idx += length
    iq = np.concatenate(segments)
    if len(iq) < n:
        iq = np.pad(iq, (0, n - len(iq)))
    return iq.astype(np.complex128)


_OOD_FN = {
    "2FSK": _generate_2fsk, "GFSK": _generate_gfsk, "OFDM": _generate_ofdm,
    "AM-DSB": _generate_am_dsb, "WBFM": _generate_wbfm, "LFM": _generate_lfm,
    "CW": _generate_cw, "MULTITONE": _generate_multitone, "PULSE": _generate_pulse,
    "FHOP": _generate_fhop,
}


def generate_ood_iq(modulation: str, config: SignalConfig | None = None,
                    rng: np.random.Generator | None = None) -> tuple[np.ndarray, dict[str, Any]]:
    """Generate one normalized complex64 OOD record + metadata (synthetic only)."""
    modulation = str(modulation).upper()
    cfg = config or SignalConfig()
    rng = rng or np.random.default_rng()
    if modulation not in _OOD_FN:
        raise ValueError(f"unsupported OOD modulation {modulation}")
    iq = _OOD_FN[modulation](rng, cfg)
    iq = _normalize_rms(iq, cfg.amplitude)
    iq = _apply_rotation(iq, cfg).astype(np.complex64)
    metadata = {
        "modulation": modulation,
        "sample_rate": cfg.sample_rate,
        "sample_length": cfg.sample_length,
        "amplitude_rms": cfg.amplitude,
        "ood_synthesis": "synthetic",
    }
    return iq, metadata


def generate_family(modulation: str, *, count: int, split_code: int, seed: int = 2026,
                    config: SignalConfig | None = None) -> tuple[np.ndarray, dict[str, Any]]:
    """Generate ``count`` deterministic samples of one modulation for one split.

    ``split_code`` selects oe_aux(0) / validation(1) / final(2); the family code is
    derived from the modulation.  Three-way isolation comes from the SeedSequence
    ``[seed, split_code, family_code]`` and per-sample child streams.
    """
    if split_code not in SPLIT_CODE.values():
        raise ValueError(f"split_code must be one of {list(SPLIT_CODE.values())}, got {split_code}")
    modulation = str(modulation).upper()
    if modulation not in FAMILY_CODE:
        raise ValueError(f"unsupported OOD modulation {modulation}")
    cfg = config or SignalConfig()

    seq = np.random.SeedSequence([int(seed), int(split_code), int(FAMILY_CODE[modulation])])
    child_seeds = seq.spawn(int(count))
    out = np.empty((int(count), 2, cfg.sample_length), dtype=np.float32)
    for i in range(int(count)):
        child = np.random.default_rng(child_seeds[i])
        iq, _ = generate_ood_iq(modulation, cfg, child)
        out[i, 0, :] = iq.real.astype(np.float32)
        out[i, 1, :] = iq.imag.astype(np.float32)

    metadata = {
        "modulation": modulation,
        "source": source_of(modulation),
        "family_code": int(FAMILY_CODE[modulation]),
        "split_code": int(split_code),
        "seed": int(seed),
        "count": int(count),
        "sample_length": cfg.sample_length,
        "sample_rate": cfg.sample_rate,
        "amplitude_rms": cfg.amplitude,
        "ood_synthesis": "synthetic",
    }
    return out, metadata


def source_of(modulation: str) -> str:
    modulation = str(modulation).upper()
    if modulation in OOD_NEAR_24:
        return "near"
    if modulation in OOD_AMBIGUOUS:
        return "ambiguous"
    if modulation in OOD_FAR:
        return "far"
    raise ValueError(f"unsupported OOD modulation {modulation}")


__all__ = [
    "OOD_NEAR_24", "OOD_AMBIGUOUS", "OOD_FAR", "FAMILY_CODE", "SPLIT_CODE",
    "SignalConfig", "root_raised_cosine_taps", "generate_ood_iq",
    "generate_family", "source_of",
]
