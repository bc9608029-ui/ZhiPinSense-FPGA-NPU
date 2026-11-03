"""Software PSD + peak detection (the CPU side of the frozen FPGA split).

The frozen FPGA contract assigns window/FFT/magnitude-square/double-buffer to
the PL and noise_floor / adaptive_threshold / bin_merge / band_stitch /
target_tracking to the CPU.  This module is the offline CPU-side reference used
by the simulation and by the ``software`` backend.  It is label-blind: it takes
raw IQ + the dwell LO and returns candidate peaks, never a class label.

Resolution rule: local maxima above the adaptive threshold are kept strongest-
first; any peak closer than RESOLVABLE_SEPARATION_BINS to a stronger peak is
merged (this is exactly the "unresolvable" case the offline test targets mark
as merged, and the scorer reports as a miss per contract sec. 8).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

import multisignal_contracts as C


@dataclass(frozen=True)
class CandidatePeak:
    """One merged bin group above the adaptive threshold."""

    lo_hz: int                 # dwell LO (tuning centre), Hz
    center_hz: int             # lo_hz + (peak_bin - 512) * BIN_HZ, Hz
    peak_bin: int              # fftshift bin index 0..1023
    peak_db: float             # PSD peak power, dB (relative scale)
    prominence_db: float       # peak minus local noise floor, dB
    occupied_bins: int         # bins within OCCUPIED_BW_DB of the peak
    bw_hz: int                 # occupied span in Hz (>= BIN_HZ)


def windowed_psd_linear(iq: np.ndarray) -> np.ndarray:
    """1024-point symmetric-Hann-windowed PSD, fftshift order, linear power."""
    x = np.asarray(iq, dtype=np.complex128)
    if x.ndim != 1 or x.size < C.FFT_LENGTH:
        raise ValueError("dwell capture shorter than one FFT frame")
    if not np.isfinite(x.real).all() or not np.isfinite(x.imag).all():
        raise ValueError("dwell capture contains non-finite IQ")
    frame = x[: C.FFT_LENGTH]
    windowed = frame * np.hanning(C.FFT_LENGTH)
    spectrum = np.fft.fftshift(np.fft.fft(windowed))
    power = np.abs(spectrum) ** 2
    return np.asarray(power, dtype=np.float64)


def psd_db(power_linear: np.ndarray, floor_frac: float = 1e-8) -> np.ndarray:
    peak = max(float(power_linear.max()), 0.0)
    floor = max(peak * floor_frac, np.finfo(np.float64).tiny)
    return 10.0 * np.log10(np.maximum(power_linear, floor))


def _noise_floor_db(db: np.ndarray, quantile: float) -> float:
    return float(np.quantile(db, quantile))


def _local_maxima(db: np.ndarray, above: np.ndarray) -> list[int]:
    maxima: list[int] = []
    n = db.size
    for i in range(1, n - 1):
        if above[i] and db[i] > db[i - 1] and db[i] >= db[i + 1]:
            maxima.append(i)
    return maxima


def _occupied_span(db: np.ndarray, peak_bin: int, occupied_db: float) -> tuple[int, int]:
    """Contiguous bin span within ``occupied_db`` of the peak (inclusive)."""
    thr = db[peak_bin] - occupied_db
    lo = peak_bin
    while lo > 0 and db[lo - 1] >= thr:
        lo -= 1
    hi = peak_bin
    while hi < db.size - 1 and db[hi + 1] >= thr:
        hi += 1
    return lo, hi


def pick_peaks(
    lo_hz: int,
    iq: np.ndarray,
    *,
    threshold_db: float = C.PEAK_THRESHOLD_DB,
    occupied_bw_db: float = C.OCCUPIED_BW_DB,
) -> list[CandidatePeak]:
    """Return merged candidate peaks above the adaptive threshold.

    Local maxima above ``median + threshold_db`` are kept strongest-first; any
    maximum whose bin falls inside a kept peak's -20 dB occupied span is merged
    into that peak (this is exactly the unresolvable overlap the offline test
    targets mark as merged).  Each survivor's centre is the power-weighted
    centroid of its occupied span (robust against the peak bin jittering
    between two nearly equal merged tones).  ``prominence_db`` of a survivor is
    its power ABOVE the adaptive median noise floor -- the numeric power value
    stored into the target record's ``power_valid`` field (relative scale, not
    dBm).
    """
    power = windowed_psd_linear(iq)
    db = psd_db(power)
    noise = _noise_floor_db(db, C.NOISE_FLOOR_QUANTILE)
    above = db >= noise + threshold_db
    maxima = _local_maxima(db, above)
    selected: list[int] = []
    spans: list[tuple[int, int]] = []
    for idx in sorted(maxima, key=lambda i: -db[i]):
        if any(lo <= idx <= hi for lo, hi in spans):
            continue
        selected.append(idx)
        spans.append(_occupied_span(db, idx, occupied_bw_db))

    candidates: list[CandidatePeak] = []
    for local_peak, (lo, hi) in zip(selected, spans):
        peak_db = float(db[local_peak])
        occupied_bins = max(1, hi - lo + 1)
        bins = np.arange(lo, hi + 1, dtype=np.float64)
        weights = power[lo : hi + 1]
        centroid_bin = float(np.sum(bins * weights) / np.sum(weights))
        center_hz = lo_hz + (centroid_bin - C.FFT_LENGTH // 2) * C.BIN_HZ
        candidates.append(
            CandidatePeak(
                lo_hz=int(lo_hz),
                center_hz=int(round(center_hz)),
                peak_bin=int(local_peak),
                peak_db=peak_db,
                prominence_db=float(peak_db - noise),
                occupied_bins=int(occupied_bins),
                bw_hz=max(C.BIN_HZ, int(occupied_bins * C.BIN_HZ)),
            )
        )
    # Return in frequency order for stable downstream behaviour.
    return sorted(candidates, key=lambda p: p.center_hz)
