"""Multi-target identity, de-duplication and aging (contract sec. 7).

The frozen target record carries exactly nine fields:
``target_id, center_hz, bw_hz, power_valid, top3, confidence, last_seen,
status, backend``.  ``target_id`` is a stable monotonic counter assigned at
first discovery and never reused within a run.  ``power_valid`` carries a
NUMERIC power measurement -- dB above the dwell's adaptive median noise floor
(relative scale, NOT dBm); see ``contracts.POWER_*`` for source/unit/range.
De-duplication merges any detection within MERGE_RADIUS_HZ of an existing
target; a target is dropped after N consecutive revisit cycles without
re-detection (N configurable, default 3).  Single-SDR sequential scan: list
timestamps are tuning times, not simultaneous identifications.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

from . import contracts as C


@dataclass
class TargetRecord:
    target_id: int
    center_hz: int
    bw_hz: int
    power_valid: float              # numeric power: dB above adaptive median
                                    # noise floor (relative scale, NOT dBm);
                                    # >= POWER_VALID_MIN_DB => valid detection;
                                    # POWER_INVALID_DB (nan) => unmeasured
    top3: list[dict[str, Any]]       # up to 3 {class_name, confidence}
    confidence: float                # top-1 confidence, 0.0 when unclassified
    last_seen: float                 # seconds, same epoch as receiver time.time()
    status: str
    backend: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AgedOutEvent:
    target_id: int
    center_hz: int
    last_seen: float


class TargetTracker:
    """Label-blind target de-dup + aging.  Classification is injected per
    target by the caller; the tracker never reads ground truth."""

    def __init__(self, aging_cycles: int = C.AGING_CYCLES_DEFAULT,
                 merge_radius_hz: int = C.MERGE_RADIUS_HZ) -> None:
        if aging_cycles < 1:
            raise ValueError("aging_cycles must be positive")
        if merge_radius_hz < 0:
            raise ValueError("merge_radius_hz must be non-negative")
        self.aging_cycles = int(aging_cycles)
        self.merge_radius_hz = int(merge_radius_hz)
        self._next_id = 1
        self._active: dict[int, TargetRecord] = {}
        self._misses: dict[int, int] = {}
        self._history: list[AgedOutEvent] = []

    # -- read-only views ------------------------------------------------------
    def active_targets(self) -> list[TargetRecord]:
        return list(self._active.values())

    def history(self) -> list[AgedOutEvent]:
        return list(self._history)

    def snapshot(self) -> list[dict[str, Any]]:
        return [t.to_dict() for t in sorted(self._active.values(),
                                            key=lambda t: t.target_id)]

    # -- per-detection update -------------------------------------------------
    def _match(self, center_hz: int) -> int | None:
        best_id: int | None = None
        best_gap = self.merge_radius_hz + 1
        for tid, rec in self._active.items():
            gap = abs(rec.center_hz - center_hz)
            if gap <= self.merge_radius_hz and gap < best_gap:
                best_gap = gap
                best_id = tid
        return best_id

    def observe(self, center_hz: int, now_seconds: float, *,
                bw_hz: int = 0, power_db: float | None = None,
                backend: str = "software") -> TargetRecord:
        if backend not in C.BACKENDS:
            raise ValueError(f"invalid backend {backend!r}")
        if center_hz <= 0 or not isinstance(center_hz, int):
            raise ValueError("center_hz must be a positive integer")
        power_valid = C.POWER_INVALID_DB if power_db is None else float(power_db)
        tid = self._match(center_hz)
        if tid is not None:
            rec = self._active[tid]
            rec.center_hz = center_hz
            if bw_hz > 0:
                rec.bw_hz = bw_hz
            rec.power_valid = power_valid
            rec.last_seen = now_seconds
            rec.backend = backend
            rec.status = "tracking"
            self._misses[tid] = 0
            return rec
        rec = TargetRecord(
            target_id=self._next_id,
            center_hz=center_hz,
            bw_hz=bw_hz,
            power_valid=power_valid,
            top3=[],
            confidence=0.0,
            last_seen=now_seconds,
            status="new",
            backend=backend,
        )
        self._next_id += 1
        self._active[rec.target_id] = rec
        self._misses[rec.target_id] = 0
        return rec

    def classify(self, target_id: int, top3: list[dict[str, Any]],
                 confidence: float) -> None:
        rec = self._active.get(target_id)
        if rec is None:
            raise KeyError(f"unknown target_id {target_id}")
        if len(top3) > 3:
            raise ValueError("top3 must have at most three entries")
        rec.top3 = list(top3)
        rec.confidence = float(confidence)

    def drop(self, target_id: int) -> TargetRecord:
        """Remove an active target (band-change cleanup) and return it."""
        rec = self._active.pop(target_id)
        self._misses.pop(target_id, None)
        return rec

    # -- end-of-cycle aging ---------------------------------------------------
    def end_cycle(self) -> list[AgedOutEvent]:
        """Mark every active target missed this cycle and expire the stale ones."""
        expired: list[AgedOutEvent] = []
        for tid in list(self._active.keys()):
            self._misses[tid] += 1
            if self._misses[tid] >= self.aging_cycles:
                rec = self._active.pop(tid)
                rec.status = "expired"
                ev = AgedOutEvent(tid, rec.center_hz, rec.last_seen)
                self._history.append(ev)
                self._misses.pop(tid, None)
                expired.append(ev)
            else:
                self._active[tid].status = "missing"
        return expired
