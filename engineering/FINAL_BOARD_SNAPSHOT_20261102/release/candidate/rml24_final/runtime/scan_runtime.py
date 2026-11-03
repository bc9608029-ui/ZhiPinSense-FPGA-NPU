"""Pure scan/detection logic for the final RML24 fixed + band-scan receiver.

The detector uses only the public repeated training block.  It never reads a
class label, a source payload, an expected prediction, or a per-sample tuning
parameter.  Classification remains the frozen Stage-7 two-DC + NPU path.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import numpy as np


SAMPLE_RATE_HZ = 2_560_000
TRAIN_REPEAT = 1024


@dataclass(frozen=True)
class ScanConfig:
    start_hz: int
    stop_hz: int
    step_hz: int = 1_000_000
    sample_rate_hz: int = SAMPLE_RATE_HZ
    min_public_score: float = 0.10
    readback_tolerance_hz: int = 5_000

    def validate(self) -> None:
        if self.start_hz <= 0 or self.stop_hz < self.start_hz:
            raise ValueError("invalid scan frequency range")
        if self.step_hz <= 0:
            raise ValueError("scan step must be positive")
        if self.sample_rate_hz <= 0:
            raise ValueError("sample rate must be positive")
        # The detector intentionally avoids the outer 5% of the complex-Nyquist
        # band.  Adjacent LO positions must overlap this usable band.
        if self.step_hz > int(0.90 * self.sample_rate_hz):
            raise ValueError("scan step leaves an uncovered frequency gap")
        if not 0.0 < self.min_public_score <= 1.0:
            raise ValueError("public-reference score must be in (0, 1]")
        if self.readback_tolerance_hz < 0:
            raise ValueError("readback tolerance must be non-negative")

    def lo_frequencies(self) -> tuple[int, ...]:
        self.validate()
        values = list(range(self.start_hz, self.stop_hz + 1, self.step_hz))
        if values[-1] != self.stop_hz:
            values.append(self.stop_hz)
        return tuple(values)


@dataclass(frozen=True)
class PublicDetection:
    start: int
    coarse_cfo_hz: float
    score: float


@dataclass(frozen=True)
class ScanHit:
    lo_hz: int
    signal_hz: float
    detection: PublicDetection
    raw_iq: np.ndarray


def _moving_sum(values: np.ndarray, width: int) -> np.ndarray:
    if width <= 0 or values.ndim != 1 or values.size < width:
        raise ValueError("invalid moving-sum request")
    prefix = np.concatenate((np.zeros(1, dtype=values.dtype), np.cumsum(values)))
    return prefix[width:] - prefix[:-width]


def _periodic_metric(raw: np.ndarray, repeat: int) -> np.ndarray:
    if raw.size < 2 * repeat:
        raise ValueError("capture is shorter than the public repeated block")
    left = raw[:-repeat]
    right = raw[repeat:]
    cross = _moving_sum(left * np.conj(right), repeat)
    e0 = _moving_sum(np.abs(left) ** 2, repeat)
    e1 = _moving_sum(np.abs(right) ** 2, repeat)
    denom = np.sqrt(np.maximum(e0 * e1, 0.0))
    metric = np.zeros(cross.size, dtype=np.float64)
    valid = denom > 1e-12
    metric[valid] = np.abs(cross[valid]) / denom[valid]
    return np.clip(metric, 0.0, 1.0)


def _candidate_starts(metric: np.ndarray, block: int = 512) -> list[int]:
    """Keep one periodic maximum per block plus a small local neighbourhood.

    The repeated payload also has a high lag-1024 metric.  Sampling every block
    prevents that long plateau from hiding the much shorter public-training peak;
    the known-reference score below then rejects payload-only candidates.
    """
    starts: set[int] = set()
    for base in range(0, metric.size, block):
        part = metric[base : base + block]
        if part.size == 0:
            continue
        peak = base + int(np.argmax(part))
        # The lag product uses half-open moving windows, so the maximum can land
        # one sample before/after the exact known-reference boundary.  Evaluate
        # that bounded neighbourhood rather than weakening the score threshold.
        for delta in (-1, 0, 1):
            candidate = peak + delta
            if 0 <= candidate < metric.size:
                starts.add(candidate)
    return sorted(starts)


def detect_public_training(
    raw_iq: np.ndarray,
    public_train: np.ndarray,
    sample_rate_hz: int = SAMPLE_RATE_HZ,
) -> PublicDetection:
    """Locate the public 2x1024 training block and estimate wide-range CFO.

    For each lag-periodic candidate, multiplying by the conjugate known training
    removes the QPSK symbols.  The strongest FFT tone estimates CFO over the full
    complex Nyquist interval; a one-lag phase estimate refines the FFT bin.
    """
    raw = np.asarray(raw_iq, dtype=np.complex128)
    train = np.asarray(public_train, dtype=np.complex128)
    if raw.ndim != 1 or train.shape != (2 * TRAIN_REPEAT,):
        raise ValueError("expected 1-D capture and a 2048-sample public train")
    if not np.isfinite(raw.real).all() or not np.isfinite(raw.imag).all():
        raise ValueError("capture contains non-finite IQ")
    if sample_rate_hz <= 0:
        raise ValueError("sample rate must be positive")

    metric = _periodic_metric(raw, TRAIN_REPEAT)
    n = np.arange(train.size, dtype=np.float64)
    train_energy = float(np.vdot(train, train).real)
    best: PublicDetection | None = None
    for start in _candidate_starts(metric):
        stop = start + train.size
        if stop > raw.size:
            continue
        segment = raw[start:stop]
        energy = float(np.vdot(segment, segment).real)
        if energy <= 1e-12:
            continue
        despread = segment * np.conj(train)
        spectrum = np.fft.fft(despread)
        peak_bin = int(np.argmax(np.abs(spectrum)))
        bin_hz = float(np.fft.fftfreq(train.size, d=1.0 / sample_rate_hz)[peak_bin])
        # Refine the FFT bin with the same repeated-half phase estimator used by
        # the verified recovery.  Unlike adjacent-sample phase, this is robust to
        # the measured Pluto passband response on the public QPSK sequence.
        segment_bin_corrected = segment * np.exp(-2j * np.pi * bin_hz * n / sample_rate_hz)
        first = segment_bin_corrected[:TRAIN_REPEAT]
        second = segment_bin_corrected[TRAIN_REPEAT:]
        lag = np.vdot(first - first.mean(), second - second.mean())
        residual_hz = (
            float(np.angle(lag) * sample_rate_hz / (2.0 * np.pi * TRAIN_REPEAT))
            if abs(lag)
            else 0.0
        )
        # Residual is only a sub-bin refinement. Clamp it defensively so a bad
        # candidate cannot jump to an unrelated ambiguity branch.
        bin_width = sample_rate_hz / train.size
        residual_hz = float(np.clip(residual_hz, -0.5 * bin_width, 0.5 * bin_width))
        cfo_hz = bin_hz + residual_hz
        carrier = np.exp(-2j * np.pi * cfo_hz * n / sample_rate_hz)
        coherent = abs(np.sum(despread * carrier))
        score = float(coherent / np.sqrt(max(energy * train_energy, 1e-24)))
        candidate = PublicDetection(start=start, coarse_cfo_hz=cfo_hz, score=min(score, 1.0))
        if best is None or candidate.score > best.score:
            best = candidate
    if best is None:
        raise RuntimeError("no finite public-reference candidate")
    return best


def remove_coarse_cfo(raw_iq: np.ndarray, cfo_hz: float, sample_rate_hz: int = SAMPLE_RATE_HZ) -> np.ndarray:
    raw = np.asarray(raw_iq)
    n = np.arange(raw.size, dtype=np.float64)
    corrected = raw * np.exp(-2j * np.pi * float(cfo_hz) * n / sample_rate_hz)
    return corrected.astype(np.complex64, copy=False)


def scan_and_select(
    config: ScanConfig,
    public_train: np.ndarray,
    tune: Callable[[int], int],
    capture: Callable[[], np.ndarray],
    flush: Callable[[], None] | None = None,
) -> tuple[ScanHit | None, list[dict[str, float | int | bool]]]:
    """Sweep all LO positions and return the strongest public-frame hit.

    Every step is retained in diagnostics.  The function has no labels and does
    not classify; its only output to the classifier is IQ corrected for a public-
    reference CFO estimate.
    """
    config.validate()
    best: ScanHit | None = None
    diagnostics: list[dict[str, float | int | bool]] = []
    for requested in config.lo_frequencies():
        actual = int(tune(requested))
        if abs(actual - requested) > config.readback_tolerance_hz:
            raise RuntimeError(f"LO readback mismatch requested={requested} actual={actual}")
        if flush is not None:
            flush()
        raw = np.asarray(capture())
        detection = detect_public_training(raw, public_train, config.sample_rate_hz)
        accepted = detection.score >= config.min_public_score
        diagnostics.append(
            {
                "requested_lo_hz": requested,
                "actual_lo_hz": actual,
                "public_start": detection.start,
                "coarse_cfo_hz": detection.coarse_cfo_hz,
                "public_score": detection.score,
                "accepted": accepted,
            }
        )
        if accepted and (best is None or detection.score > best.detection.score):
            best = ScanHit(
                lo_hz=actual,
                signal_hz=float(actual + detection.coarse_cfo_hz),
                detection=detection,
                raw_iq=raw.copy(),
            )
    return best, diagnostics


def coverage_intervals(config: ScanConfig) -> tuple[tuple[float, float], ...]:
    config.validate()
    half = 0.45 * config.sample_rate_hz
    return tuple((lo - half, lo + half) for lo in config.lo_frequencies())


def has_full_coverage(config: ScanConfig) -> bool:
    intervals = coverage_intervals(config)
    cursor = float(config.start_hz)
    for low, high in intervals:
        if low > cursor:
            return False
        cursor = max(cursor, high)
    return cursor >= config.stop_hz

