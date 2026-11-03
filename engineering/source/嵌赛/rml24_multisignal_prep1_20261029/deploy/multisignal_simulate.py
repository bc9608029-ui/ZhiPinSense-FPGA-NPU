"""Offline sequential-scan simulation with multi-target tracking (task 5).

A synthetic single-SDR receiver sweeps LO points, forms a PSD per dwell,
extracts candidate peaks, and feeds them to the :class:`TargetTracker`.  The
classifier is an injected callable; the simulator, tracker and scorer never
read ground truth.  This lets the scoring contract be exercised against
0/1/2/3-target, edge, entry/exit, power and resolution scenarios without RF.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np

import multisignal_contracts as C
import multisignal_psd
from multisignal_scoring import GroundTruthTarget
from multisignal_tracker import TargetTracker

Classifier = Callable[[int, np.ndarray], tuple[list[dict[str, Any]], float]]


@dataclass
class ScenarioTarget:
    """One ground-truth emitter inside the simulation."""

    truth: GroundTruthTarget
    bw_hz: int = 8_000


class Simulator:
    """Synthetic sequential scanner.  Never reads ground truth for detection."""

    def __init__(
        self,
        start_hz: int,
        stop_hz: int,
        step_hz: int,
        truth: list[GroundTruthTarget],
        *,
        target_bw_hz: int = 8_000,
        noise_rms: float = 1.0,
        sample_rate_hz: int = C.SAMPLE_RATE_HZ,
        capture_samples: int = C.CAPTURE_SAMPLES,
        aging_cycles: int = C.AGING_CYCLES_DEFAULT,
        seed: int = 0,
    ) -> None:
        C.validate_scan_step_hz(step_hz)
        if start_hz <= 0 or stop_hz < start_hz:
            raise ValueError("invalid scan range")
        self.start_hz = int(start_hz)
        self.stop_hz = int(stop_hz)
        self.step_hz = int(step_hz)
        self.truth = list(truth)
        self.target_bw_hz = int(target_bw_hz)
        self.noise_rms = float(noise_rms)
        self.sample_rate_hz = int(sample_rate_hz)
        self.capture_samples = int(capture_samples)
        self.rng = np.random.default_rng(seed)
        self.tracker = TargetTracker(aging_cycles=aging_cycles)
        self.observations: list[dict[str, Any]] = []
        self._lo_points = list(range(self.start_hz, self.stop_hz + 1, self.step_hz))
        if self._lo_points[-1] != self.stop_hz:
            self._lo_points.append(self.stop_hz)

    # -- synthetic RF ------------------------------------------------ -------
    def active_targets(self, now_seconds: float) -> list[ScenarioTarget]:
        return [
            ScenarioTarget(t, self.target_bw_hz)
            for t in self.truth
            if t.entry_seconds <= now_seconds < t.exit_seconds
        ]

    def dwell_iq(self, lo_hz: int, now_seconds: float) -> np.ndarray:
        """Synthetic baseband capture at ``lo_hz`` (label-blind, content-only).

        Each active target is a deterministic narrowband-carrier stand-in (a
        pure tone at its centre offset).  This pins the PSD peak exactly at the
        target centre so the tracker/scorer tests exercise identity, aging and
        resolution rather than PSD peak jitter; PSD resolution itself is tested
        separately against the frozen envelope in ``test_psd``.
        """
        t = np.arange(self.capture_samples, dtype=np.float64) / self.sample_rate_hz
        x = self.noise_rms * (
            self.rng.standard_normal(self.capture_samples)
            + 1j * self.rng.standard_normal(self.capture_samples)
        )
        for st in self.active_targets(now_seconds):
            offset = float(st.truth.center_hz - lo_hz)
            if abs(offset) > 0.5 * C.USABLE_BAND_FRACTION * self.sample_rate_hz:
                continue
            amp = 10.0 ** (st.truth.power_db / 20.0)
            x = x + amp * np.exp(2j * np.pi * offset * t)
        return np.asarray(x, dtype=np.complex128)

    # -- scan loop ------------------------------------------------------------
    def run_cycle(self, cycle_seconds: float,
                  classifier: Classifier | None = None) -> None:
        """One full sequential sweep + aging.

        Every dwell feeds candidate peaks to the tracker (de-dup by frequency);
        classification runs once per NEW target.  One observation per target
        per cycle is recorded for scoring, so revisit intervals measure
        across cycles rather than across overlapping dwells.
        """
        seen_ids: set[int] = set()
        for lo in self._lo_points:
            now = cycle_seconds
            iq = self.dwell_iq(lo, now)
            for peak in psd.pick_peaks(lo, iq):
                rec = self.tracker.observe(
                    peak.center_hz, now, bw_hz=peak.bw_hz,
                    power_db=peak.prominence_db,
                    backend="software",
                )
                if classifier is not None and rec.status == "new":
                    top3, conf = classifier(rec.center_hz, iq)
                    self.tracker.classify(rec.target_id, top3, conf)
                seen_ids.add(rec.target_id)
        active_by_id = {t.target_id: t for t in self.tracker.active_targets()}
        for tid in sorted(seen_ids):
            rec = active_by_id[tid]
            self.observations.append({
                "target_id": rec.target_id,
                "center_hz": rec.center_hz,
                "last_seen": rec.last_seen,
                "top3": list(rec.top3),
                "confidence": rec.confidence,
            })
        self.tracker.end_cycle()

    def run(self, n_cycles: int, cycle_seconds: float,
            classifier: Classifier | None = None) -> TargetTracker:
        """Run ``n_cycles`` sweeps at times ``1..n * cycle_seconds``."""
        for i in range(n_cycles):
            self.run_cycle((i + 1) * cycle_seconds, classifier)
        return self.tracker
