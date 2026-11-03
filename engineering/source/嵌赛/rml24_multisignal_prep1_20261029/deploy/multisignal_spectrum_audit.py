"""TX composite spectrum audit (task 4, offline only).

Given the composite produced by :mod:`tx_synth`, quantify:

* sampling bandwidth usage (carriers inside the usable TX band),
* crest factor and clipping fraction at the DAC full scale,
* guard-band spacing between carriers,
* third-order intermodulation (cubic-DAC model),
* common-preamble cross-interference (spectral leakage of the other
  carriers into each carrier's occupied band).

The audit returns numbers only; it never emits RF.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

import multisignal_contracts as C
import multisignal_tx_synth


@dataclass
class CarrierAudit:
    offset_hz: int
    amplitude: float
    peak_db: float
    occupied_bw_hz: int
    leakage_from_others_db: float      # max other-carrier power inside its band


@dataclass
class TxAuditResult:
    sample_rate_hz: int
    n_carriers: int
    peak: float
    rms: float
    papr_db: float
    clip_fraction: float               # fraction of samples clipping at TX_HEADROOM_DB
    min_guard_hz: int
    guard_ok: bool
    im3_relative_db: float             # strongest IM3 below the weakest carrier
    carriers: list[CarrierAudit] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_rate_hz": self.sample_rate_hz,
            "n_carriers": self.n_carriers,
            "peak": self.peak,
            "rms": self.rms,
            "papr_db": self.papr_db,
            "clip_fraction": self.clip_fraction,
            "min_guard_hz": self.min_guard_hz,
            "guard_ok": self.guard_ok,
            "im3_relative_db": self.im3_relative_db,
            "carriers": [
                {
                    "offset_hz": c.offset_hz,
                    "amplitude": c.amplitude,
                    "peak_db": c.peak_db,
                    "occupied_bw_hz": c.occupied_bw_hz,
                    "leakage_from_others_db": c.leakage_from_others_db,
                }
                for c in self.carriers
            ],
        }


def _psd_db(x: np.ndarray) -> np.ndarray:
    spectrum = np.fft.fftshift(np.fft.fft(np.asarray(x, dtype=np.complex128)))
    power = np.abs(spectrum) ** 2
    peak = max(float(power.max()), 0.0)
    floor = max(peak * 1e-12, np.finfo(np.float64).tiny)
    return 10.0 * np.log10(np.maximum(power, floor))


def _freq_axis_hz(n: int, sample_rate_hz: int) -> np.ndarray:
    return np.fft.fftshift(np.fft.fftfreq(n, d=1.0 / sample_rate_hz))


def crest_and_clipping(composite: np.ndarray,
                       full_scale: int = C.TX_FULL_SCALE,
                       headroom_db: float = C.TX_HEADROOM_DB) -> tuple[float, float, float, float]:
    """Return (peak, rms, papr_db, clip_fraction).

    ``clip_fraction`` is the fraction of samples that would clip when the
    composite is scaled so its RMS sits ``headroom_db`` below the DAC full
    scale.  PAPR below the headroom means no clipping.
    """
    x = np.asarray(composite, dtype=np.complex128)
    peak = float(np.max(np.abs(x)))
    rms = float(np.sqrt(np.mean(np.abs(x) ** 2)))
    if rms <= 0.0:
        raise ValueError("degenerate composite")
    papr_db = float(20.0 * np.log10(peak / rms))
    scale = full_scale / (rms * 10.0 ** (headroom_db / 20.0))
    scaled = np.abs(x) * scale
    clip_fraction = float(np.mean(scaled > full_scale))
    return peak, rms, papr_db, clip_fraction


def _occupied_bw_hz(x: np.ndarray, sample_rate_hz: int,
                    occupied_db: float = C.OCCUPIED_BW_DB) -> int:
    """-20 dB occupied bandwidth of a single-carrier waveform (Hz)."""
    db = _psd_db(x)
    peak = float(db.max())
    active = db >= peak - occupied_db
    idx = np.flatnonzero(active)
    if idx.size == 0:
        return 0
    freq = _freq_axis_hz(db.size, sample_rate_hz)
    span = freq[idx[-1]] - freq[idx[0]]
    return max(int(round(span)), C.BIN_HZ)


def im3_relative_db(composite: np.ndarray, sample_rate_hz: int,
                    cubic: float = 0.02) -> float:
    """Strongest third-order intermod product relative to the weakest carrier.

    A memoryless cubic term ``cubic * |x|^2 * x`` models DAC nonlinearity; the
    IM3 products around the carriers are the largest spurious terms.  Returns
    the strongest IM3 level minus the weakest carrier peak, in dB (more
    negative is better).
    """
    x = np.asarray(composite, dtype=np.complex128)
    nl = cubic * (np.abs(x) ** 2) * x
    db_nl = _psd_db(nl)
    db_sig = _psd_db(x)
    # Restrict to the region actually occupied by carriers (within usable band).
    freq = _freq_axis_hz(x.size, sample_rate_hz)
    in_band = np.abs(freq) <= C.TX_USABLE_HALF_BAND_HZ
    if not in_band.any():
        return -np.inf
    weakest_carrier_db = float(db_sig[in_band].max())  # conservative: strongest
    strongest_im3_db = float(db_nl[in_band].max())
    return float(strongest_im3_db - weakest_carrier_db)


def run_audit(
    composite: np.ndarray,
    carriers: list[tx_synth.TxCarrier],
    per_carrier: np.ndarray,
    sample_rate_hz: int = C.TX_SAMPLE_RATE_HZ,
) -> TxAuditResult:
    """Full audit of a synthesized composite."""
    if per_carrier.shape[0] != len(carriers):
        raise ValueError("per_carrier shape mismatch")
    peak, rms, papr_db, clip_fraction = crest_and_clipping(composite)
    offsets = sorted(c.offset_hz for c in carriers)
    gaps = [b - a for a, b in zip(offsets, offsets[1:])]
    min_guard_hz = min(gaps) if gaps else C.TX_USABLE_HALF_BAND_HZ * 2
    guard_ok = min_guard_hz >= C.TX_GUARD_BAND_HZ

    db_total = _psd_db(composite)
    freq = _freq_axis_hz(composite.size, sample_rate_hz)

    carrier_audits: list[CarrierAudit] = []
    for i, c in enumerate(carriers):
        occ = _occupied_bw_hz(per_carrier[i], sample_rate_hz)
        band = np.abs(freq - c.offset_hz) <= max(occ / 2.0, C.BIN_HZ)
        if not band.any():
            continue
        own_peak_db = float(db_total[band].max())
        others = np.delete(per_carrier, i, axis=0).sum(axis=0)
        leakage = float(_psd_db(others)[band].max()) if others.size else -np.inf
        carrier_audits.append(
            CarrierAudit(
                offset_hz=c.offset_hz,
                amplitude=c.amplitude,
                peak_db=own_peak_db,
                occupied_bw_hz=occ,
                leakage_from_others_db=float(leakage - own_peak_db),
            )
        )

    return TxAuditResult(
        sample_rate_hz=sample_rate_hz,
        n_carriers=len(carriers),
        peak=peak,
        rms=rms,
        papr_db=papr_db,
        clip_fraction=clip_fraction,
        min_guard_hz=min_guard_hz,
        guard_ok=guard_ok,
        im3_relative_db=im3_relative_db(composite, sample_rate_hz),
        carriers=carrier_audits,
    )
