"""Dual-Pluto TX digital-domain synthesis (task 4, offline only).

One TX Pluto + one RX Pluto.  To present several signals simultaneously within
a single TX instantaneous bandwidth, the TX digitally sums K frequency-shifted
copies of the *same* public frame payload.  This module only builds the
baseband composite; :mod:`spectrum_audit` checks sampling bandwidth, crest
factor/clipping, guard band, intermodulation and common-preamble cross-talk.

Honesty boundary: signals that live in different tuning bands or beyond the
single TX instantaneous bandwidth require extra hardware.  Rapid TX retuning
that visits one carrier at a time is NOT simultaneous multi-signal and is not
what this module produces.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from . import contracts as C

# Offline test target: a carrier is treated as narrowband only if its
# occupied bandwidth is at most this many bins, so that two carriers separated
# by RESOLVABLE_SEPARATION_HZ (an offline test target, board-verify pending)
# do not intrinsically overlap.  The real deployed public-frame occupied
# bandwidth must be measured on the board; the offline default symbol rate
# below is a conservative stand-in.
MAX_CARRIER_OCCUPIED_BW_HZ: int = 4 * C.BIN_HZ          # 10_000 (4 bins)
DEFAULT_SYMBOL_RATE_HZ: int = 8_000                     # -> occupied bw ~ 8 kHz


@dataclass
class TxCarrier:
    """One digitally frequency-shifted carrier within the TX passband.

    ``offset_hz`` is relative to the TX LO; ``amplitude`` is the linear per-
    carrier amplitude before clipping.  ``frame`` defaults to a shared
    unit-RMS common frame (the same public preamble + payload), which is what
    makes cross-interference a pure spectral-leakage question.
    """

    offset_hz: int
    amplitude: float = 1.0
    frame: np.ndarray | None = None

    def __post_init__(self) -> None:
        if not -C.TX_USABLE_HALF_BAND_HZ <= self.offset_hz <= C.TX_USABLE_HALF_BAND_HZ:
            raise ValueError(
                f"carrier offset {self.offset_hz} Hz outside usable TX half-band"
            )
        if self.amplitude <= 0.0:
            raise ValueError("carrier amplitude must be positive")


def make_common_frame(
    rng: np.random.Generator | None = None,
    samples: int = C.FRAME_SAMPLES,
    symbol_rate_hz: int = DEFAULT_SYMBOL_RATE_HZ,
    sample_rate_hz: int = C.TX_SAMPLE_RATE_HZ,
) -> np.ndarray:
    """Unit-RMS representative common frame (public preamble + payload).

    QPSK symbols at ``symbol_rate_hz``, zero-order-held and lightly smoothed,
    give a controlled occupied bandwidth (about one symbol rate) so the audit
    is reproducible.  The deployed public QPSK sequence is class/session
    specific; crest-factor, clipping, guard-band, IM3 and cross-talk audits
    depend only on spectral occupancy and RMS level.
    """
    if samples < C.PUBLIC_TRAIN_SAMPLES:
        raise ValueError("frame shorter than public training block")
    if symbol_rate_hz <= 0 or symbol_rate_hz > sample_rate_hz:
        raise ValueError("symbol_rate_hz out of range")
    rng = rng if rng is not None else np.random.default_rng(0)
    sps = max(1, int(round(sample_rate_hz / symbol_rate_hz)))
    nsym = max(1, samples // sps)
    symbols = rng.choice(
        np.array([1 + 1j, 1 - 1j, -1 + 1j, -1 - 1j]) / np.sqrt(2.0), size=nsym
    )
    held = np.repeat(symbols, sps)
    kernel = np.ones(4, dtype=np.float64) / 4.0
    shaped = np.convolve(held, kernel, mode="same")
    shaped = shaped[:samples]
    if shaped.size < samples:
        shaped = np.pad(shaped, (0, samples - shaped.size))
    rms = float(np.sqrt(np.mean(np.abs(shaped) ** 2)))
    if rms <= 0.0:
        raise RuntimeError("degenerate common frame")
    return np.asarray(shaped / rms, dtype=np.complex128)


def synthesize(
    carriers: list[TxCarrier],
    sample_rate_hz: int = C.TX_SAMPLE_RATE_HZ,
    shared_frame: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Sum the carriers into one baseband composite.

    Returns ``(composite, per_carrier_iq)`` where ``per_carrier_iq`` is the
    stacked pre-sum, per-carrier waveform for the audit (shape (K, N)).
    """
    if not carriers:
        raise ValueError("at least one carrier required")
    frames: list[np.ndarray] = []
    lengths: set[int] = set()
    for c in carriers:
        frame = c.frame if c.frame is not None else (
            shared_frame if shared_frame is not None else make_common_frame()
        )
        frame = np.asarray(frame, dtype=np.complex128)
        lengths.add(frame.size)
        frames.append(frame)
    if len(lengths) != 1:
        raise ValueError("all carriers must use the same frame length")
    n = frames[0].size
    t = np.arange(n, dtype=np.float64) / float(sample_rate_hz)
    stacked = np.empty((len(carriers), n), dtype=np.complex128)
    for i, c in enumerate(carriers):
        phase = np.exp(2j * np.pi * float(c.offset_hz) * t)
        stacked[i] = c.amplitude * frames[i] * phase
    composite = stacked.sum(axis=0)
    return composite, stacked


def to_int16_clipped(
    composite: np.ndarray, full_scale: int = C.TX_FULL_SCALE
) -> tuple[np.ndarray, float]:
    """Scale to the DAC int16 range and clip, returning (interleaved_i16, scale)."""
    peak = float(np.max(np.abs(composite)))
    if peak <= 0.0:
        raise ValueError("empty composite")
    scale = full_scale / peak
    interleaved = np.empty(2 * composite.size, dtype=np.int16)
    interleaved[0::2] = np.rint(composite.real * scale).clip(-full_scale, full_scale).astype(np.int16)
    interleaved[1::2] = np.rint(composite.imag * scale).clip(-full_scale, full_scale).astype(np.int16)
    return interleaved, scale


def carrier_summary(carrier: TxCarrier) -> dict[str, Any]:
    return {"offset_hz": carrier.offset_hz, "amplitude": carrier.amplitude}
