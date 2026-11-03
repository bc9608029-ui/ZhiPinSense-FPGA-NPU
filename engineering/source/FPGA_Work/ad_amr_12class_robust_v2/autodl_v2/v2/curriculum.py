"""SNR curriculum schedules for V2 Phase A training.

A curriculum restricts the SNR grid presented to the trainer over epochs.  It
never changes the label; it only changes which SNR rows are sampled while the
underlying dataset generation stays deterministic per (seed, split, epoch, idx).
"""

from __future__ import annotations

from typing import Any

import numpy as np


def _grid(snr_values: list[float]) -> np.ndarray:
    return np.asarray([float(v) for v in snr_values], dtype=np.float64)


def active_snr_values(schedule: str, snr_values: list[float], epoch: int,
                      total_epochs: int) -> list[float]:
    """Return the SNR values exposed at the given epoch.

    ``schedule`` is one of ``none`` (default), ``very_low_first``,
    ``linear_warmup``.
    """
    grid = _grid(snr_values)
    if schedule in (None, "", "none", "flat"):
        return grid.tolist()

    if schedule == "very_low_first":
        # First half of training sees only SNR <= -2 dB, then the full grid.
        if epoch <= max(1, total_epochs // 2):
            return [float(v) for v in grid if v <= -2.0]
        return grid.tolist()

    if schedule == "linear_warmup":
        # Gradually widen from the low-SNR half to the full grid.
        low_half = [float(v) for v in grid if v <= 0.0]
        full = grid.tolist()
        progress = min(1.0, max(0.0, epoch / max(1, total_epochs)))
        if progress <= 0.0:
            return low_half
        high_half = [float(v) for v in full if v > 0.0]
        keep = int(round(len(high_half) * progress))
        return low_half + high_half[:keep]

    raise ValueError(f"unknown snr_curriculum schedule {schedule!r}")
