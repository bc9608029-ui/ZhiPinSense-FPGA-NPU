"""Multi-signal scan-loop scheduler for the REAL software entry (task 1/3/5).

This module is the offline reference the main thread merges into
``standalone_receiver.py``.  It replaces the single ``best``/``locked`` collapse
with a fair, label-blind multi-target scheduler (contract sec. 7).

Honesty contract (matches ``docs/INTEGRATION_LAYER.md``):

* The real per-dwell primitive ``detect_public_training`` returns ONE detection
  per capture, so one dwell contributes at most one candidate from that
  primitive.  A software PSD backend (``psd.pick_peaks``) can contribute several
  candidates from ONE capture; that is the "same-capture multi-signal" path and
  is wired via :meth:`sweep_psd` (gated on the same ``software`` backend
  contract; the FPGA path remains on the B line).
* The multi-target list therefore grows ACROSS sequential LO dwells (list
  timestamps are tuning times) and/or from PSD multi-peak dwells; it is never a
  claim of simultaneous identification.
* The correlation detector produces no PSD power, so ``power_db`` defaults to
  ``None`` (unmeasured) and the record's ``power_valid`` field stays NaN until a
  PSD-capable backend fills it.

Scheduling semantics (task 3):

* **Candidate queue** -- every newly observed target is queued for
  classification; ``classify_pass`` drains the queue round-robin.
* **Revisit budget** -- ``revisit`` re-detects at most ``revisit_budget``
  targets per cycle (0 = unlimited), round-robin, so one strong signal cannot
  monopolise every cycle.
* **Fair scheduling** -- both classification and revisit rotate across targets
  instead of always picking the strongest ``best``.
* **Periodic full-band rescan** -- ``due_for_rescan(cycle)`` is true every
  ``rescan_every_cycles`` cycles so new entrants are found even while targets
  are being revisited.
* **last_seen vs last_classified** -- ``last_seen`` (frozen record field) is the
  last DETECTION time; ``last_classified`` is scheduler-side diagnostic and is
  NOT a record field.
* **Band-change cleanup/migration** -- ``apply_range`` drops targets whose
  centre falls outside the new band (cleanup) and re-homes the rest to the
  nearest new LO (migration); the removed list is deterministic and logged.

This module imports only the C-line packages (``contracts``/``tracker``/``psd``)
and a pluggable detect callable; it imports NOTHING from the A/B trees.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

import numpy as np

import multisignal_contracts as C
from multisignal_tracker import TargetRecord, TargetTracker

# detect(raw_iq) -> object with .score (float) and .coarse_cfo_hz (float),
# exactly like scan_runtime.PublicDetection.
Detector = Callable[[np.ndarray], Any]
# psd_detect(lo_hz, raw_iq) -> list[CandidatePeak] (psd.pick_peaks signature).
PsdDetector = Callable[[int, np.ndarray], list[Any]]
# tune(hz) -> actual_hz ; capture() -> raw_iq ; flush() -> None | None
Tuner = Callable[[int], int]
Capturer = Callable[[], np.ndarray]
# classify(center_hz, raw_iq) -> (top3: list[{class_name, confidence}], conf: float)
Classifier = Callable[[int, np.ndarray], tuple[list[dict[str, Any]], float]]


@dataclass
class ScanLoopOptions:
    """Config for the tracker-driven multi-signal scheduler."""

    min_public_score: float = C.MIN_PUBLIC_SCORE
    max_coarse_cfo_hz: float = 1000.0      # locked re-check acceptance (matches entry)
    aging_cycles: int = C.AGING_CYCLES_DEFAULT
    merge_radius_hz: int = C.MERGE_RADIUS_HZ
    backend: str = "software"
    rescan_every_cycles: int = 1           # full-band rescan every N cycles
    revisit_budget: int = 0                # max dwells per revisit pass (0 = unlimited)
    classify_budget: int = 0               # max classifications per pass (0 = unlimited)
    band_edge_margin_hz: int = 0           # extra margin for band-change cleanup


class MultiSignalScanLoop:
    """Fair, label-blind multi-target scheduler (replaces ``best``/``locked``)."""

    def __init__(self, lo_points: list[int], options: ScanLoopOptions | None = None) -> None:
        self.lo_points = [int(lo) for lo in lo_points]
        self.opts = options or ScanLoopOptions()
        if self.opts.rescan_every_cycles < 1:
            raise ValueError("rescan_every_cycles must be >= 1")
        if self.opts.revisit_budget < 0 or self.opts.classify_budget < 0:
            raise ValueError("budgets must be non-negative")
        self.tracker = TargetTracker(aging_cycles=self.opts.aging_cycles,
                                     merge_radius_hz=self.opts.merge_radius_hz)
        self.observations: list[dict[str, Any]] = []
        self._target_lo: dict[int, int] = {}            # target_id -> last verified LO
        self._queued: dict[int, None] = {}              # classification queue (ordered)
        self._last_classified: dict[int, float] = {}    # target_id -> seconds (diagnostic)
        self._removed: list[dict[str, Any]] = []        # cleanup/migration log
        self._cycle: int = 0

    # -- control -------------------------------------------------------------
    def apply_range(self, lo_points: list[int]) -> list[dict[str, Any]]:
        """Range modification: rebuild the schedule; cleanup/migrate targets.

        Deterministic rule: a target whose centre falls outside the new band
        (plus ``band_edge_margin_hz``) is DROPPED (cleanup) and logged; every
        target still inside is re-homed to the nearest new LO (migration).
        """
        self.lo_points = [int(lo) for lo in lo_points]
        removed: list[dict[str, Any]] = []
        if not self.lo_points:
            # Empty band: drop everything.
            for tid in list(self.tracker._active):
                rec = self.tracker.drop(tid)
                rec.status = "expired"
                removed.append({"target_id": tid, "center_hz": rec.center_hz,
                                "reason": "empty_band"})
                self._forget(tid)
        else:
            lo_min, lo_max = min(self.lo_points), max(self.lo_points)
            margin = self.opts.band_edge_margin_hz
            for tid in list(self.tracker._active):
                rec = self.tracker._active[tid]
                if rec.center_hz < lo_min - margin or rec.center_hz > lo_max + margin:
                    self.tracker.drop(tid)
                    rec.status = "expired"
                    removed.append({"target_id": tid, "center_hz": rec.center_hz,
                                    "reason": "outside_new_band"})
                    self._forget(tid)
                else:
                    self._target_lo[tid] = min(
                        self.lo_points, key=lambda lo: abs(lo - rec.center_hz)
                    )
        self._removed.extend(removed)
        return removed

    def _forget(self, target_id: int) -> None:
        self._queued.pop(target_id, None)
        self._target_lo.pop(target_id, None)
        self._last_classified.pop(target_id, None)

    # -- detection helpers ---------------------------------------------------
    def _detect(self, raw: np.ndarray, detector: Detector) -> tuple[float, float]:
        d = detector(raw)
        return float(d.score), float(d.coarse_cfo_hz)

    def observe_candidate(self, lo_hz: int, cfo_hz: float, now: float,
                          *, bw_hz: int = 0, power_db: float | None = None) -> TargetRecord:
        """Feed one correlation detection (LO + CFO) into the tracker."""
        center_hz = int(round(float(lo_hz) + cfo_hz))
        rec = self._observe(center_hz, lo_hz, now, bw_hz=bw_hz, power_db=power_db)
        return rec

    def observe_peak(self, peak: Any, lo_hz: int, now: float) -> TargetRecord:
        """Feed one PSD candidate peak (absolute centre) into the tracker."""
        rec = self._observe(int(peak.center_hz), lo_hz, now,
                            bw_hz=int(peak.bw_hz), power_db=float(peak.prominence_db))
        return rec

    def _observe(self, center_hz: int, lo_hz: int, now: float, *,
                 bw_hz: int, power_db: float | None) -> TargetRecord:
        rec = self.tracker.observe(
            center_hz, now, bw_hz=bw_hz, power_db=power_db, backend=self.opts.backend
        )
        self._target_lo[rec.target_id] = int(lo_hz)
        if rec.target_id not in self._last_classified:
            self._queued.setdefault(rec.target_id, None)
        return rec

    # -- sweep: insertion point 1 (replaces the single ``best`` collapse) ----
    def sweep(self, detector: Detector, tune: Tuner, capture: Capturer,
              flush: Callable[[], None] | None, now: float,
              should_stop: Callable[[], bool] | None = None) -> list[int]:
        """Full-band scan; feed EVERY accepted dwell hit into the tracker.

        Returns the target_ids newly created during this sweep.  ``should_stop``
        (mirroring the real loop's ``stop.is_set()``) is polled at each dwell
        boundary; a stopped sweep returns early and keeps whatever it already
        found.
        """
        new_ids: list[int] = []
        for lo in self.lo_points:
            if should_stop is not None and should_stop():
                break
            actual = int(tune(lo))
            if flush is not None:
                flush()
            raw = np.asarray(capture())
            score, cfo = self._detect(raw, detector)
            if score < self.opts.min_public_score:
                continue
            rec = self.observe_candidate(actual, cfo, now)
            if rec.status == "new":
                new_ids.append(rec.target_id)
        return new_ids

    # -- sweep_psd: same-capture multi-candidate (software PSD backend) ------
    def sweep_psd(self, psd_detect: PsdDetector, tune: Tuner, capture: Capturer,
                  flush: Callable[[], None] | None, now: float,
                  should_stop: Callable[[], bool] | None = None) -> list[int]:
        """One dwell can contribute SEVERAL candidates via the software PSD path.

        ``psd_detect(lo_hz, raw)`` returns the merged candidate peaks
        (``psd.pick_peaks``); each survivor is observed with its measured PSD
        power (``power_valid`` = prominence dB) and occupied bandwidth.  This is
        the same ``software`` backend contract, NOT a claim that the
        correlation primitive returns multiple hits.
        """
        new_ids: list[int] = []
        for lo in self.lo_points:
            if should_stop is not None and should_stop():
                break
            actual = int(tune(lo))
            if flush is not None:
                flush()
            raw = np.asarray(capture())
            for peak in psd_detect(actual, raw):
                rec = self.observe_peak(peak, actual, now)
                if rec.status == "new":
                    new_ids.append(rec.target_id)
        return new_ids

    # -- classification: fair RR drain of the candidate queue ----------------
    def classify_pass(self, classify: Classifier, tune: Tuner, capture: Capturer,
                      flush: Callable[[], None] | None, now: float,
                      should_stop: Callable[[], bool] | None = None,
                      budget: int | None = None) -> list[int]:
        """Round-robin classification of queued targets, budget-limited.

        Returns the target_ids classified this pass.  A target whose LO is gone
        is skipped (and re-queued on its next observation).  ``last_classified``
        is updated on success only.
        """
        budget = self.opts.classify_budget if budget is None else int(budget)
        done: list[int] = []
        n = 0
        for tid in list(self._queued):
            if should_stop is not None and should_stop():
                break
            if budget and n >= budget:
                break
            rec = self.tracker._active.get(tid)
            if rec is None:
                self._queued.pop(tid, None)
                continue
            lo = self._target_lo.get(tid)
            if lo is None:
                continue
            actual = int(tune(lo))
            if flush is not None:
                flush()
            raw = np.asarray(capture())
            top3, conf = classify(rec.center_hz, raw)
            self.tracker.classify(tid, top3, conf)
            self._last_classified[tid] = now
            self._queued.pop(tid, None)
            done.append(tid)
            n += 1
        return done

    # -- revisit: fair re-detection of tracking targets (insertion point 2) --
    def revisit(self, detector: Detector, tune: Tuner, capture: Capturer,
                flush: Callable[[], None] | None, now: float,
                should_stop: Callable[[], bool] | None = None,
                budget: int | None = None) -> list[int]:
        """Re-tune/re-detect tracking targets round-robin; misses age via end_cycle.

        Returns the target_ids that re-detected this cycle.
        """
        budget = self.opts.revisit_budget if budget is None else int(budget)
        hit_ids: list[int] = []
        n = 0
        for rec in self.tracker.active_targets():
            if should_stop is not None and should_stop():
                break
            if budget and n >= budget:
                break
            if rec.status == "expired":
                continue
            lo = self._target_lo.get(rec.target_id)
            if lo is None:
                continue
            actual = int(tune(lo))
            if flush is not None:
                flush()
            raw = np.asarray(capture())
            score, cfo = self._detect(raw, detector)
            n += 1
            if score >= self.opts.min_public_score and abs(cfo) <= self.opts.max_coarse_cfo_hz:
                self.observe_candidate(actual, cfo, now)
                hit_ids.append(rec.target_id)
        return hit_ids

    # -- cycle end: aging (expired cleanup) + rescan gating ------------------
    def due_for_rescan(self, cycle_index: int) -> bool:
        """True when ``cycle_index`` (1-based) is a full-band rescan cycle.

        The first cycle always rescans, then every ``rescan_every_cycles``
        cycles (cycle 1, 1+N, 1+2N, ...).
        """
        return (cycle_index - 1) % self.opts.rescan_every_cycles == 0

    def end_cycle(self) -> list[Any]:
        """Record observations for every active target, then age the misses."""
        self._cycle += 1
        for rec in self.tracker.active_targets():
            self.observations.append({
                "target_id": rec.target_id,
                "center_hz": rec.center_hz,
                "last_seen": rec.last_seen,
                "last_classified": self._last_classified.get(rec.target_id),
                "top3": list(rec.top3),
                "confidence": rec.confidence,
            })
        return self.tracker.end_cycle()

    # -- views ---------------------------------------------------------------
    def active_targets(self) -> list[TargetRecord]:
        return self.tracker.active_targets()

    def snapshot(self) -> list[dict[str, Any]]:
        return self.tracker.snapshot()

    def pending_classification(self) -> list[int]:
        return list(self._queued)

    def removed_log(self) -> list[dict[str, Any]]:
        return list(self._removed)

    def last_classified_of(self, target_id: int) -> float | None:
        return self._last_classified.get(target_id)
