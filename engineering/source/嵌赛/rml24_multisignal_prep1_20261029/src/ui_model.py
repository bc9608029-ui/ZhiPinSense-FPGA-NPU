"""Offline UI state model for the multi-target list (task 2 UI plan).

The existing five-page UI renders one result at a time (single top1 + top3 +
one spectrum + one constellation).  The multi-signal extension adds a result
LIST and per-target selection.  This module models that state and its two
frozen rules:

* spectrum/waterfall are drawn in SCAN coordinates (bin index -> centre Hz via
  ``lo_hz + (bin - 512) * BIN_HZ``) and carry the dwell tuning time;
* the constellation shows only the SELECTED target's valid IQ, and switching
  targets clears the previous plot.

This is display logic only; it never touches RF.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from . import contracts as C
from .tracker import TargetRecord


@dataclass
class SpectrumFrame:
    """One dwell's PSD in scan coordinates, tagged with its tuning time."""

    lo_hz: int
    tune_time_seconds: float
    psd_db: np.ndarray              # 1024 bins, fftshift order
    backend_effective: str = "software"

    def __post_init__(self) -> None:
        if self.psd_db.ndim != 1 or self.psd_db.size != C.FFT_LENGTH:
            raise ValueError("spectrum must be 1024 fftshift bins")
        if self.backend_effective not in ("software", "fpga"):
            raise ValueError("invalid effective backend")

    def freq_axis_hz(self) -> np.ndarray:
        bins = np.arange(C.FFT_LENGTH, dtype=np.int64)
        return self.lo_hz + (bins - C.FFT_LENGTH // 2) * C.BIN_HZ

    def center_hz(self, bin_index: int) -> int:
        return int(self.lo_hz + (int(bin_index) - C.FFT_LENGTH // 2) * C.BIN_HZ)


@dataclass
class UiMultiSignalState:
    """Offline model of the multi-target list page."""

    targets: list[dict[str, Any]]
    selected_target_id: int | None
    spectrum: SpectrumFrame | None
    constellation_iq: np.ndarray | None   # valid IQ of the selected target only

    @staticmethod
    def empty() -> "UiMultiSignalState":
        return UiMultiSignalState([], None, None, None)

    def refresh(self, targets: list[TargetRecord],
                spectrum: SpectrumFrame | None) -> None:
        self.targets = [t.to_dict() for t in targets]
        if spectrum is not None:
            self.spectrum = spectrum
        # A vanished selection falls back to none and clears the constellation.
        if self.selected_target_id is not None and not any(
            t.target_id == self.selected_target_id for t in targets
        ):
            self.selected_target_id = None
            self.constellation_iq = None

    def select(self, target_id: int, constellation_iq: np.ndarray | None) -> None:
        """Select a target; the constellation is replaced, never accumulated."""
        if not any(t["target_id"] == target_id for t in self.targets):
            raise KeyError(f"unknown target_id {target_id}")
        self.selected_target_id = int(target_id)
        self.constellation_iq = (
            None if constellation_iq is None
            else np.asarray(constellation_iq, dtype=np.complex128).copy()
        )

    def clear_constellation(self) -> None:
        self.constellation_iq = None
