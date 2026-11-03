"""Flat-deployed multi-signal scoring (test-only; mirrors C-line src/scoring.py).

Detection and classification are reported SEPARATELY; a missed target is a fixed
error and is never dropped from the denominator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import multisignal_contracts as C


@dataclass
class GroundTruthTarget:
    truth_id: int
    center_hz: int
    class_name: str
    entry_seconds: float
    exit_seconds: float          # math.inf while still active at end
    power_db: float = 0.0        # truth-side relative amplitude, dB (amplitude
                                 # = 10**(power_db/20)); relative scale, NOT dBm
    bw_hz: int = 0


@dataclass
class ClassificationReport:
    classified: int = 0
    correct: int = 0
    wrong: int = 0
    unclassified_matched: int = 0
    accuracy: float = 0.0        # correct / classified (0.0 when none)


@dataclass
class ScoreReport:
    expected_targets: int = 0
    detected_targets: int = 0
    detection_rate: float = 0.0
    missed_truth_ids: list[int] = field(default_factory=list)
    false_alarm_target_ids: list[int] = field(default_factory=list)
    duplicate_groups: list[dict[str, Any]] = field(default_factory=list)
    first_discovery_seconds: dict[int, float] = field(default_factory=dict)
    revisit_intervals_seconds: dict[int, list[float]] = field(default_factory=dict)
    classification: ClassificationReport = field(default_factory=ClassificationReport)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "expected_targets": self.expected_targets,
            "detected_targets": self.detected_targets,
            "detection_rate": self.detection_rate,
            "missed_truth_ids": self.missed_truth_ids,
            "false_alarm_target_ids": self.false_alarm_target_ids,
            "duplicate_groups": self.duplicate_groups,
            "first_discovery_seconds": self.first_discovery_seconds,
            "revisit_intervals_seconds": self.revisit_intervals_seconds,
            "classification": {
                "classified": self.classification.classified,
                "correct": self.classification.correct,
                "wrong": self.classification.wrong,
                "unclassified_matched": self.classification.unclassified_matched,
                "accuracy": self.classification.accuracy,
            },
        }
        return out


def _match_truth(center_hz: int, truth: list[GroundTruthTarget],
                 radius_hz: int) -> GroundTruthTarget | None:
    best: GroundTruthTarget | None = None
    best_gap = radius_hz + 1
    for t in truth:
        gap = abs(center_hz - t.center_hz)
        if gap <= radius_hz and gap < best_gap:
            best_gap = gap
            best = t
    return best


def score(
    truth: list[GroundTruthTarget],
    observations: list[dict[str, Any]],
    *,
    match_radius_hz: int = C.MERGE_RADIUS_HZ,
    time_window: tuple[float, float] | None = None,
) -> ScoreReport:
    """Score a run.

    ``observations`` is a list of per-detection rows produced by the tracker
    and simulator, each with at least:
      target_id, center_hz, last_seen (seconds), top3 (list of
      {class_name, confidence}), confidence.
    """
    t0, t1 = time_window if time_window is not None else (float("-inf"), float("inf"))
    obs = [o for o in observations if t0 <= float(o["last_seen"]) < t1]

    report = ScoreReport()
    report.expected_targets = len(truth)

    # Group observations by target_id, preserving time order.
    by_target: dict[int, list[dict[str, Any]]] = {}
    for o in sorted(obs, key=lambda r: float(r["last_seen"])):
        by_target.setdefault(int(o["target_id"]), []).append(o)

    matched_truth_ids: set[int] = set()
    truth_obs: dict[int, list[dict[str, Any]]] = {}
    duplicate_groups: list[dict[str, Any]] = []
    unmatched_target_ids: list[int] = []

    for tid, rows in by_target.items():
        centers = [int(r["center_hz"]) for r in rows]
        center_median = int(sorted(centers)[len(centers) // 2])
        matched: GroundTruthTarget | None = None
        for t in truth:
            if not (t.entry_seconds <= float(rows[-1]["last_seen"]) < t.exit_seconds):
                continue
            if abs(center_median - t.center_hz) <= match_radius_hz:
                matched = t
                break
        if matched is None:
            unmatched_target_ids.append(tid)
            continue
        matched_truth_ids.add(matched.truth_id)
        if matched.truth_id in truth_obs:
            duplicate_groups.append({
                "truth_id": matched.truth_id,
                "target_ids": sorted([truth_obs[matched.truth_id][0]["target_id"], tid]),
            })
        truth_obs.setdefault(matched.truth_id, []).extend(rows)

    report.detected_targets = len(matched_truth_ids)
    report.detection_rate = (report.detected_targets / report.expected_targets
                             if report.expected_targets else 0.0)
    report.missed_truth_ids = sorted(
        t.truth_id for t in truth if t.truth_id not in matched_truth_ids
    )
    report.false_alarm_target_ids = sorted(unmatched_target_ids)
    report.duplicate_groups = duplicate_groups

    for t in truth:
        rows = truth_obs.get(t.truth_id)
        if not rows:
            continue
        first = float(rows[0]["last_seen"])
        report.first_discovery_seconds[t.truth_id] = max(0.0, first - t.entry_seconds)
        times = sorted(float(r["last_seen"]) for r in rows)
        intervals = [b - a for a, b in zip(times, times[1:])]
        report.revisit_intervals_seconds[t.truth_id] = intervals

    cls = ClassificationReport()
    for tid, rows in by_target.items():
        centers = [int(r["center_hz"]) for r in rows]
        center_median = int(sorted(centers)[len(centers) // 2])
        matched = _match_truth(center_median, truth, match_radius_hz)
        if matched is None or matched.truth_id not in matched_truth_ids:
            continue
        last = rows[-1]
        top3 = last.get("top3") or []
        if not top3:
            cls.unclassified_matched += 1
            continue
        cls.classified += 1
        if top3[0].get("class_name") == matched.class_name:
            cls.correct += 1
        else:
            cls.wrong += 1
    cls.accuracy = (cls.correct / cls.classified) if cls.classified else 0.0
    report.classification = cls
    return report
