"""Fair multi-target scheduler tests (C3): candidate queue, revisit budget,
fair RR classification, periodic rescan, band-change cleanup/migration,
last_seen vs last_classified.  These drive the scheduler directly with a
label-blind stand-in detector/classifier (no RF, no NPU)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pytest

from src.scan_adapter import MultiSignalScanLoop, ScanLoopOptions
from src.psd import pick_peaks


@dataclass
class Det:
    score: float
    coarse_cfo_hz: float


class FakeRadio:
    """Minimal tune/capture/flush; capture content is irrelevant for these tests."""

    def __init__(self) -> None:
        self.lo = 0
        self.tuned: list[int] = []

    def tune(self, hz: int) -> int:
        self.lo = int(hz)
        self.tuned.append(self.lo)
        return self.lo

    def flush(self) -> None:
        pass

    def capture(self) -> np.ndarray:
        return np.zeros(1024, dtype=np.complex128)


def _hit_detector(score: float = 0.5, cfo: float = 0.0):
    return lambda raw: Det(score, cfo)


def _label_blind(center_hz, raw):
    return [{"class_name": f"cls@{center_hz}", "confidence": 0.9}], 0.9


# --- candidate queue + classification --------------------------------------
def test_sweep_enqueues_and_classify_pass_drains():
    radio = FakeRadio()
    loop = MultiSignalScanLoop([2_399_000_000, 2_400_000_000, 2_401_000_000])
    det = _hit_detector()
    new_ids = loop.sweep(det, radio.tune, radio.capture, radio.flush, 1.0)
    assert new_ids == [1, 2, 3]
    assert loop.pending_classification() == [1, 2, 3]
    done = loop.classify_pass(_label_blind, radio.tune, radio.capture, radio.flush, 1.0)
    assert done == [1, 2, 3]
    assert loop.pending_classification() == []
    for tid in (1, 2, 3):
        assert loop.last_classified_of(tid) == 1.0


def test_classify_budget_round_robin():
    radio = FakeRadio()
    loop = MultiSignalScanLoop([2_399_000_000, 2_400_000_000, 2_401_000_000],
                               ScanLoopOptions(classify_budget=1))
    loop.sweep(_hit_detector(), radio.tune, radio.capture, radio.flush, 1.0)
    # Budget 1: each pass classifies exactly one target, in queue order.
    assert loop.classify_pass(_label_blind, radio.tune, radio.capture, radio.flush, 1.0) == [1]
    assert loop.classify_pass(_label_blind, radio.tune, radio.capture, radio.flush, 2.0) == [2]
    assert loop.classify_pass(_label_blind, radio.tune, radio.capture, radio.flush, 3.0) == [3]
    assert loop.pending_classification() == []


# --- revisit budget / fairness ----------------------------------------------
def test_revisit_budget_round_robin():
    radio = FakeRadio()
    loop = MultiSignalScanLoop([2_399_000_000, 2_400_000_000, 2_401_000_000],
                               ScanLoopOptions(revisit_budget=1))
    loop.sweep(_hit_detector(), radio.tune, radio.capture, radio.flush, 1.0)
    loop.classify_pass(_label_blind, radio.tune, radio.capture, radio.flush, 1.0)
    loop.end_cycle()
    # One target missed each cycle (budget 1 of 3) -> each target ages one miss.
    hit1 = loop.revisit(_hit_detector(), radio.tune, radio.capture, radio.flush, 2.0)
    assert len(hit1) == 1
    hit2 = loop.revisit(_hit_detector(), radio.tune, radio.capture, radio.flush, 3.0)
    assert len(hit2) == 1


# --- periodic rescan --------------------------------------------------------
def test_due_for_rescan_gating():
    loop = MultiSignalScanLoop([2_400_000_000], ScanLoopOptions(rescan_every_cycles=3))
    assert [loop.due_for_rescan(i) for i in range(1, 8)] == [True, False, False,
                                                             True, False, False, True]


# --- band-change cleanup / migration ----------------------------------------
def test_apply_range_cleanup_and_migration():
    radio = FakeRadio()
    loop = MultiSignalScanLoop([2_399_000_000, 2_400_000_000, 2_401_000_000])
    loop.sweep(_hit_detector(), radio.tune, radio.capture, radio.flush, 1.0)
    assert sorted(t.center_hz for t in loop.active_targets()) == \
        [2_399_000_000, 2_400_000_000, 2_401_000_000]

    # Narrow band keeps only the middle target; the others are cleaned up.
    removed = loop.apply_range([2_400_000_000])
    assert sorted(r["reason"] for r in removed) == ["outside_new_band", "outside_new_band"]
    assert sorted(t.center_hz for t in loop.active_targets()) == [2_400_000_000]
    assert loop.removed_log() == removed

    # Migration: a target inside a shifted band is re-homed to the nearest LO.
    loop2 = MultiSignalScanLoop([2_400_000_000])
    loop2.sweep(_hit_detector(), radio.tune, radio.capture, radio.flush, 1.0)
    loop2.apply_range([2_399_000_000, 2_400_000_000, 2_401_000_000])
    assert len(loop2.active_targets()) == 1  # still inside, not dropped
    assert loop2.removed_log() == []


# --- last_seen vs last_classified ------------------------------------------
def test_last_seen_and_last_classified_are_distinct():
    radio = FakeRadio()
    loop = MultiSignalScanLoop([2_400_000_000])
    loop.sweep(_hit_detector(), radio.tune, radio.capture, radio.flush, 1.0)
    rec = loop.active_targets()[0]
    assert rec.last_seen == 1.0
    assert loop.last_classified_of(rec.target_id) is None      # not classified yet
    loop.classify_pass(_label_blind, radio.tune, radio.capture, radio.flush, 2.0)
    assert loop.last_classified_of(rec.target_id) == 2.0
    # Re-detect updates last_seen but not last_classified.
    loop.revisit(_hit_detector(), radio.tune, radio.capture, radio.flush, 3.0)
    assert loop.active_targets()[0].last_seen == 3.0
    assert loop.last_classified_of(rec.target_id) == 2.0


# --- fairness: two targets both get classified, not monopolised -------------
def test_two_targets_fair_classification():
    radio = FakeRadio()
    loop = MultiSignalScanLoop([2_399_000_000, 2_400_000_000])
    loop.sweep(_hit_detector(), radio.tune, radio.capture, radio.flush, 1.0)
    loop.classify_pass(_label_blind, radio.tune, radio.capture, radio.flush, 1.0)
    tops = {t.target_id: t.top3[0]["class_name"] for t in loop.active_targets()}
    assert set(tops.values()) == {"cls@2399000000", "cls@2400000000"}


# --- software PSD multi-candidate (C4 hook, self-contained) -----------------
def _tone_capture(lo_hz: int, offsets: list[int], n: int = 4096) -> np.ndarray:
    """Superimposed narrow-band tones at LO+offset (explainable occupancy)."""
    x = np.zeros(n, dtype=np.complex128)
    for off in offsets:
        x += np.exp(2j * np.pi * off * np.arange(n) / 2_560_000)
    return x


def test_sweep_psd_multi_candidate_same_capture():
    radio = FakeRadio()
    loop = MultiSignalScanLoop([2_400_000_000])
    # Three tones far apart (>= 5 bins = 12.5 kHz) in ONE capture -> 3 targets.
    offsets = [-50_000, 0, +50_000]

    def radio_capture_with_tones():
        return _tone_capture(radio.lo, offsets)

    new_ids = loop.sweep_psd(pick_peaks, radio.tune, radio_capture_with_tones,
                             radio.flush, 1.0)
    assert len(new_ids) == 3
    centers = sorted(t.center_hz for t in loop.active_targets())
    assert centers[1] == 2_400_000_000
    assert centers[0] < centers[1] < centers[2]
    # PSD path records measured power (numeric power_valid, not NaN).
    for t in loop.active_targets():
        assert not np.isnan(t.power_valid)
        assert t.power_valid >= 14.0
