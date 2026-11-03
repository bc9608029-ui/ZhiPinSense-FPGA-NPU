"""Verify the REAL public-frame occupied bandwidth (task 4).

The public train/tail are defined verbatim in the A-line recovery module
``candidate_two_dc.py`` (read-only): a deterministic QPSK sequence
(``np.random.default_rng(9011)``) at ONE SYMBOL PER SAMPLE (fs = 2.56 MHz).
This script regenerates them exactly and measures their occupied bandwidth so
the earlier ``<=10 kHz`` narrowband stand-in can be confirmed or retracted.

Offline only: no RF, no board.  It reproduces the TX waveform definition from
source, it does not transmit.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

FS = 2_560_000
FFT = 1024
BIN_HZ = FS / FFT


def regenerate_public_blocks() -> dict[str, np.ndarray]:
    rng = np.random.default_rng(9011)
    pn = np.exp(1j * (np.pi / 4 + np.pi / 2 * rng.integers(0, 4, 1024))).astype(np.complex64)
    train = np.tile(pn, 2)                                   # 2048 samples
    tail = np.exp(1j * (np.pi / 4 + np.pi / 2 * rng.integers(0, 4, 2048))).astype(np.complex64)
    return {"train": train, "tail": tail}


def occupied_metrics(x: np.ndarray, label: str) -> dict[str, float]:
    # Average over Hann-windowed FFT frames (Welch-like) to smooth the white
    # full-rate QPSK spectrum.
    hop = FFT // 2
    frames = [x[i : i + FFT] * np.hanning(FFT) for i in range(0, x.size - FFT + 1, hop)]
    if not frames:
        raise ValueError(f"{label}: block shorter than one FFT frame")
    power = np.mean([np.abs(np.fft.fftshift(np.fft.fft(f))) ** 2 for f in frames], axis=0)
    power = np.asarray(power, dtype=np.float64)
    total = float(power.sum())
    peak = float(power.max())

    db = 10.0 * np.log10(np.maximum(power, peak * 1e-12))
    floor_db = float(np.median(db))
    active = db >= floor_db - 20.0
    occupied_bins = int(active.sum())
    occupied_hz = occupied_bins * BIN_HZ

    # Cumulative power bandwidth (90% / 99%).
    idx = np.argsort(power)[::-1]
    cum = np.cumsum(power[idx])
    def frac_bw(frac: float) -> float:
        k = int(np.searchsorted(cum, frac * total))
        return float((k + 1) * BIN_HZ)
    return {
        "label": label,
        "samples": int(x.size),
        "peak_bin_db": float(db.max()),
        "median_bin_db": floor_db,
        "occupied_bw_hz_minus20db": float(occupied_hz),
        "occupied_bw_frac_minus20db": float(occupied_hz / FS),
        "bw_90pct_hz": frac_bw(0.90),
        "bw_99pct_hz": frac_bw(0.99),
        "bw_99pct_frac": float(frac_bw(0.99) / FS),
    }


def main() -> int:
    out_dir = Path(__file__).resolve().parents[1] / "results"
    out_dir.mkdir(exist_ok=True)
    blocks = regenerate_public_blocks()
    rows = [occupied_metrics(v, k) for k, v in blocks.items()]
    for row in rows:
        print(
            f"{row['label']:6s} samples={row['samples']:5d} "
            f"occupied-20dB={row['occupied_bw_hz_minus20db']/1000:.0f} kHz "
            f"({row['occupied_bw_frac_minus20db']:.2f} of fs) "
            f"bw99%={row['bw_99pct_hz']/1000:.0f} kHz ({row['bw_99pct_frac']:.2f} of fs)",
            flush=True,
        )
    payload = {
        "kind": "RML24_PUBLIC_BW_VERIFICATION_V1",
        "fs_hz": FS,
        "note": "train/tail regenerated verbatim from candidate_two_dc.py (seed 9011); one QPSK symbol per sample => full-band",
        "blocks": rows,
    }
    (out_dir / "public_bw_verification.json").write_text(
        json.dumps(payload, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
