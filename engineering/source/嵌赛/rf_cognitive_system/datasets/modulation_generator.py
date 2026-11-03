"""Deterministic-capable synthetic complex-baseband modulation generator."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from scipy import signal


SUPPORTED_MODULATIONS = ("BPSK", "QPSK", "8PSK", "16QAM", "64QAM", "2FSK", "CPFSK", "OFDM")


@dataclass(frozen=True)
class SignalConfig:
    sample_rate: float = 128_000.0
    symbol_rate: float = 16_000.0
    samples_per_symbol: int = 8
    sample_length: int = 1024
    amplitude: float = 1.0
    frequency_offset: float = 0.0
    phase_offset: float = 0.0
    rolloff: float = 0.35
    span_symbols: int = 8

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> "SignalConfig":
        pulse = config.get("pulse_shape", {})
        return cls(
            sample_rate=float(config.get("sample_rate", 128_000.0)),
            symbol_rate=float(config.get("symbol_rate", 16_000.0)),
            samples_per_symbol=int(config.get("samples_per_symbol", 8)),
            sample_length=int(config.get("sample_length", 1024)),
            amplitude=float(config.get("amplitude", 1.0)),
            frequency_offset=float(config.get("frequency_offset", 0.0)),
            phase_offset=float(config.get("phase_offset", 0.0)),
            rolloff=float(pulse.get("rolloff", 0.35)),
            span_symbols=int(pulse.get("span_symbols", 8)),
        )


def root_raised_cosine_taps(samples_per_symbol: int, span_symbols: int = 8, rolloff: float = 0.35) -> np.ndarray:
    """Return unit-energy root-raised-cosine FIR taps."""
    if samples_per_symbol < 2 or span_symbols < 2:
        raise ValueError("samples_per_symbol and span_symbols must be >= 2")
    if not 0.0 <= rolloff <= 1.0:
        raise ValueError("rolloff must be in [0, 1]")
    count = span_symbols * samples_per_symbol
    time = np.arange(-count / 2, count / 2 + 1, dtype=np.float64) / samples_per_symbol
    taps = np.empty_like(time)
    beta = rolloff
    for index, value in enumerate(time):
        if np.isclose(value, 0.0):
            taps[index] = 1.0 - beta + 4.0 * beta / np.pi
        elif beta > 0 and np.isclose(abs(value), 1.0 / (4.0 * beta)):
            taps[index] = (beta / np.sqrt(2.0)) * (
                (1.0 + 2.0 / np.pi) * np.sin(np.pi / (4.0 * beta))
                + (1.0 - 2.0 / np.pi) * np.cos(np.pi / (4.0 * beta))
            )
        else:
            numerator = np.sin(np.pi * value * (1.0 - beta))
            numerator += 4.0 * beta * value * np.cos(np.pi * value * (1.0 + beta))
            denominator = np.pi * value * (1.0 - (4.0 * beta * value) ** 2)
            taps[index] = numerator / denominator
    return taps / np.sqrt(np.sum(taps**2))


def _gray_pam_levels(bits: int) -> np.ndarray:
    size = 2**bits
    binary = np.arange(size)
    gray = binary ^ (binary >> 1)
    levels = np.arange(-(size - 1), size, 2, dtype=np.float64)
    result = np.empty(size, dtype=np.float64)
    result[gray] = levels
    return result


def constellation_points(modulation: str) -> np.ndarray:
    """Return the normalized ideal constellation for PSK/QAM tests and mapping."""
    modulation = modulation.upper()
    if modulation == "BPSK":
        return np.array([1.0, -1.0], dtype=np.complex128)
    if modulation == "QPSK":
        return np.array([1 + 1j, -1 + 1j, -1 - 1j, 1 - 1j], dtype=np.complex128) / np.sqrt(2.0)
    if modulation == "8PSK":
        return np.exp(1j * 2.0 * np.pi * np.arange(8) / 8.0)
    if modulation in {"16QAM", "64QAM"}:
        side = 4 if modulation == "16QAM" else 8
        levels = _gray_pam_levels(int(np.log2(side)))
        points = np.array([i + 1j * q for q in levels for i in levels], dtype=np.complex128)
        return points / np.sqrt(np.mean(np.abs(points) ** 2))
    raise ValueError(f"{modulation} does not use a finite PSK/QAM constellation")


def _pulse_shaped_symbols(symbols: np.ndarray, config: SignalConfig, timing_offset: int = 0) -> np.ndarray:
    taps = root_raised_cosine_taps(config.samples_per_symbol, config.span_symbols, config.rolloff)
    shaped = signal.upfirdn(taps, symbols, up=config.samples_per_symbol)
    group_delay = (len(taps) - 1) // 2
    required = config.sample_length
    # Skip a full filter span of already-populated symbols. This makes the
    # record boundaries a crop from a continuous stream, not a zero-padded FIR
    # startup signature that a classifier could exploit.
    start = group_delay + config.span_symbols * config.samples_per_symbol + timing_offset
    cropped = shaped[start : start + required]
    if len(cropped) < required:
        cropped = np.pad(cropped, (0, required - len(cropped)))
    return cropped.astype(np.complex128, copy=False)


def _fsk_from_symbols(
    symbols: np.ndarray,
    samples_per_symbol: int,
    sample_rate: float,
    tone_separation_hz: float,
    initial_phase: float = 0.0,
) -> np.ndarray:
    """Generate continuous-phase binary FSK from symbols in {-1,+1}."""
    instantaneous_frequency = np.repeat(symbols, samples_per_symbol) * tone_separation_hz / 2.0
    phase_step = 2.0 * np.pi * instantaneous_frequency / sample_rate
    phase = initial_phase + np.concatenate(([0.0], np.cumsum(phase_step[:-1])))
    return np.exp(1j * phase)


def _generate_ofdm(rng: np.random.Generator, config: SignalConfig, ofdm: dict[str, Any]) -> tuple[np.ndarray, dict[str, Any]]:
    fft_length = int(ofdm.get("fft_length", 64))
    cyclic_prefix = int(ofdm.get("cyclic_prefix", 16))
    active_count = int(ofdm.get("active_subcarriers", 48))
    if active_count >= fft_length or active_count % 2:
        raise ValueError("active_subcarriers must be even and smaller than fft_length")
    half = active_count // 2
    active_bins = np.concatenate((np.arange(-half, 0), np.arange(1, half + 1)))
    block_length = fft_length + cyclic_prefix
    record_offset = int(rng.integers(0, block_length))
    blocks = int(np.ceil((config.sample_length + record_offset) / block_length)) + 1
    output: list[np.ndarray] = []
    qpsk = constellation_points("QPSK")
    for _ in range(blocks):
        frequency_domain = np.zeros(fft_length, dtype=np.complex128)
        data = qpsk[rng.integers(0, len(qpsk), size=active_count)]
        frequency_domain[active_bins % fft_length] = data
        time_domain = np.fft.ifft(frequency_domain) * np.sqrt(fft_length)
        output.append(np.concatenate((time_domain[-cyclic_prefix:], time_domain)))
    iq = np.concatenate(output)[record_offset : record_offset + config.sample_length]
    metadata = {
        "fft_length": fft_length,
        "cyclic_prefix": cyclic_prefix,
        "active_subcarriers": active_count,
        "subcarrier_modulation": "QPSK",
        "record_offset_within_ofdm_symbol": record_offset,
        "occupied_bandwidth_hz_approx": active_count * config.sample_rate / fft_length,
    }
    return iq, metadata


def _normalize_rms(iq: np.ndarray, amplitude: float) -> np.ndarray:
    rms = np.sqrt(np.mean(np.abs(iq) ** 2))
    if rms <= np.finfo(np.float64).eps:
        raise ValueError("Generated waveform has zero power")
    return iq * (amplitude / rms)


def generate_iq(
    modulation: str,
    config: dict[str, Any] | SignalConfig,
    rng: np.random.Generator | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """Generate one normalized complex64 IQ record and serializable metadata."""
    modulation = modulation.upper()
    if modulation not in SUPPORTED_MODULATIONS:
        raise ValueError(f"Unsupported modulation {modulation}; expected {SUPPORTED_MODULATIONS}")
    rng = rng or np.random.default_rng()
    raw_config = config if isinstance(config, dict) else {}
    cfg = SignalConfig.from_dict(config) if isinstance(config, dict) else config
    expected_rate = cfg.symbol_rate * cfg.samples_per_symbol
    if not np.isclose(expected_rate, cfg.sample_rate, rtol=1e-6):
        raise ValueError("sample_rate must equal symbol_rate * samples_per_symbol")

    extra: dict[str, Any] = {}
    if modulation in {"BPSK", "QPSK", "8PSK", "16QAM", "64QAM"}:
        timing_offset = int(rng.integers(0, cfg.samples_per_symbol))
        points = constellation_points(modulation)
        symbol_count = int(np.ceil((cfg.sample_length + timing_offset) / cfg.samples_per_symbol)) + 2 * cfg.span_symbols + 4
        symbols = points[rng.integers(0, len(points), size=symbol_count)]
        iq = _pulse_shaped_symbols(symbols, cfg, timing_offset)
        extra.update({
            "constellation_size": len(points),
            "record_timing_offset_samples": timing_offset,
            "symbol_center_offset_samples": (-timing_offset) % cfg.samples_per_symbol,
            "occupied_bandwidth_hz_approx": (1.0 + cfg.rolloff) * cfg.symbol_rate,
            "rrc_warmup_symbols_before_record": cfg.span_symbols,
        })
    elif modulation in {"2FSK", "CPFSK"}:
        timing_offset = int(rng.integers(0, cfg.samples_per_symbol))
        symbol_count = int(np.ceil((cfg.sample_length + timing_offset) / cfg.samples_per_symbol)) + 1
        symbols = 2 * rng.integers(0, 2, size=symbol_count) - 1
        modulation_index = 1.0 if modulation == "2FSK" else 0.5
        separation = modulation_index * cfg.symbol_rate
        iq = _fsk_from_symbols(symbols, cfg.samples_per_symbol, cfg.sample_rate, separation)
        iq = iq[timing_offset : timing_offset + cfg.sample_length]
        extra.update({
            "modulation_index": modulation_index,
            "tone_separation_hz": separation,
            "record_timing_offset_samples": timing_offset,
            "symbol_center_offset_samples": (-timing_offset) % cfg.samples_per_symbol,
        })
    else:
        iq, extra = _generate_ofdm(rng, cfg, raw_config.get("ofdm", {}))

    iq = _normalize_rms(iq, cfg.amplitude)
    n = np.arange(cfg.sample_length, dtype=np.float64)
    rotation = np.exp(1j * (2.0 * np.pi * cfg.frequency_offset * n / cfg.sample_rate + cfg.phase_offset))
    iq = (iq * rotation).astype(np.complex64)
    metadata: dict[str, Any] = {
        "modulation": modulation,
        "sample_rate": cfg.sample_rate,
        "symbol_rate": cfg.symbol_rate,
        "samples_per_symbol": cfg.samples_per_symbol,
        "sample_length": cfg.sample_length,
        "amplitude_rms": cfg.amplitude,
        "frequency_offset_hz": cfg.frequency_offset,
        "phase_offset_rad": cfg.phase_offset,
        "pulse_shape": "RRC" if modulation not in {"2FSK", "CPFSK", "OFDM"} else "continuous_phase/OFDM",
        **extra,
    }
    return iq, metadata
