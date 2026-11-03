"""Real-entry replay tests (task 3): exercise the REAL production modules.

The real scan front-end (``scan_runtime.detect_public_training``), the real UI
event adapter (``ui_event.build_ui_event``/``build_board_ui_result``), the real
control server (``standalone_control.Controller``), the real lock policy
(``scan_lock_policy.LockHysteresis``) and the real recovery entry
(``receiver_core.recover_frame`` + ``candidate_two_dc.recover``) are driven
offline with synthetic captures.  The only C-line piece is the multi-signal
adapter under test (``src.scan_adapter``), which replaces the single ``best``/
``locked`` collapse in ``standalone_receiver.py``.

No RF, no board, no NPU: the NPU ``infer`` is stubbed with a label-blind
constant classifier so the multi-target wiring (detect -> track -> classify ->
UI event) is exercised end to end.

The real modules are vendored verbatim under ``reference/`` (see README there).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))     # real vendored modules
sys.path.insert(0, str(ROOT))                   # src/ packages

from candidate_two_dc import train as PUBLIC_TRAIN, tail as PUBLIC_TAIL, recover as RECOVER  # noqa: E402
from receiver_core import CLASS_NAMES, recover_frame  # noqa: E402
from scan_runtime import ScanConfig, detect_public_training  # noqa: E402
from scan_lock_policy import LockHysteresis  # noqa: E402
from standalone_control import Controller  # noqa: E402
from ui_event import build_board_ui_result, build_ui_event  # noqa: E402

from src.scan_adapter import MultiSignalScanLoop, ScanLoopOptions  # noqa: E402
from src.scoring import GroundTruthTarget, score  # noqa: E402

FS = 2_560_000
CAPTURE = 65_536


# --- synthetic emitter / capture -------------------------------------------
class Emitter:
    def __init__(self, center_hz: int, class_name: str, start: int = 8192):
        self.center_hz = int(center_hz)
        self.class_name = class_name
        self.start = int(start)


def _payload() -> np.ndarray:
    rng = np.random.default_rng(7)
    return np.exp(1j * (np.pi / 4 + np.pi / 2 * rng.integers(0, 4, 1024))).astype(np.complex64)


def _frame(cfo_hz: float) -> np.ndarray:
    train = np.asarray(PUBLIC_TRAIN, dtype=np.complex128)
    tail = np.asarray(PUBLIC_TAIL, dtype=np.complex128)
    payload = _payload()
    body = np.concatenate([np.zeros(2048), train, np.tile(payload, 8), tail, np.zeros(2048)])
    n = np.arange(body.size, dtype=np.float64)
    return body * np.exp(2j * np.pi * float(cfo_hz) * n / FS)


def make_capture(lo_hz: int, emitters: list[Emitter], *,
                 noise_rms: float = 0.01, home_map: dict | None = None) -> np.ndarray:
    """Synthetic dwell capture.

    ``home_map`` (emitter -> nearest LO) is a CONTROLLED SCHEDULING FIXTURE: it
    models the sequential-scan ownership of each emitter, so a signal is only
    present in the dwell whose LO is closest to it.  This matches the real
    per-dwell primitive (ONE detection per capture) and is NOT evidence of
    simultaneous same-capture reception -- that case is covered separately in
    ``test_same_capture_multisignal.py``.  Without ``home_map`` every in-band
    emitter is injected (single-emitter sanity tests).
    """
    x = np.zeros(CAPTURE, dtype=np.complex128)
    for e in emitters:
        if home_map is not None and home_map[e] != int(lo_hz):
            continue
        cfo = float(e.center_hz - lo_hz)
        if abs(cfo) > 0.45 * FS:
            continue
        body = _frame(cfo)
        stop = e.start + body.size
        if stop > CAPTURE:
            continue
        x[e.start:stop] += body
    if noise_rms > 0:
        rng = np.random.default_rng(123)
        x = x + noise_rms * (rng.standard_normal(CAPTURE) + 1j * rng.standard_normal(CAPTURE))
    return np.asarray(x, dtype=np.complex128)


def _label_blind_classifier(center_hz, raw):
    # NPU stand-in: constant QPSK; label-blind (never reads ground truth).
    return [{"class_name": "QPSK", "confidence": 0.9}], 0.9


class ReplayRadio:
    """Synthetic tune/capture/flush with the exact production call signature."""

    def __init__(self, emitters: list[Emitter], lo_points: list[int] | None = None):
        self.emitters = emitters
        self.lo = 0
        self.home_map: dict | None = None
        if lo_points is not None:
            los = [int(l) for l in lo_points]
            self.home_map = {e: min(los, key=lambda l: abs(l - e.center_hz)) for e in emitters}

    def tune(self, hz: int) -> int:
        self.lo = int(hz)
        return self.lo

    def flush(self) -> None:
        pass

    def capture(self) -> np.ndarray:
        return make_capture(self.lo, self.emitters, home_map=self.home_map)


def _run(emitters, lo_points, cycles=2, cycle_seconds=1.0):
    radio = ReplayRadio(emitters, lo_points)
    loop = MultiSignalScanLoop(lo_points)
    detector = lambda raw: detect_public_training(np.asarray(raw), PUBLIC_TRAIN)  # noqa: E731
    for i in range(cycles):
        now = (i + 1) * cycle_seconds
        loop.sweep(detector, radio.tune, radio.capture, radio.flush, now)
        loop.classify_pass(_label_blind_classifier, radio.tune, radio.capture,
                           radio.flush, now)
        loop.end_cycle()
    return loop


def _truth(*specs):
    return [GroundTruthTarget(tid, hz, cls, entry, exit_)
            for tid, hz, cls, entry, exit_ in specs]


# --- detection front-end sanity (real detector on synthetic frame) ---------
def test_real_detector_finds_synthetic_public_frame():
    lo = 2_400_000_000
    emitters = [Emitter(2_400_000_000, "QPSK", start=8192)]
    raw = make_capture(lo, emitters)
    d = detect_public_training(raw, PUBLIC_TRAIN)
    assert d.score >= 0.10
    assert abs(d.coarse_cfo_hz) < 500.0       # frame at CFO 0


def test_real_detector_estimates_cfo():
    lo = 2_400_000_000
    emitters = [Emitter(2_400_250_000, "BPSK", start=8192)]   # +250 kHz CFO
    raw = make_capture(lo, emitters)
    d = detect_public_training(raw, PUBLIC_TRAIN)
    assert d.score >= 0.10
    assert abs(d.coarse_cfo_hz - 250_000) < 2_000


# --- 0 / 1 / 2 / 3 targets -------------------------------------------------
# NOTE (C4 scope): the 2/3-target tests below use the home_map CONTROLLED
# SCHEDULING FIXTURE -- each emitter appears only at its nearest LO dwell.  They
# prove the sequential-scan scheduler, NOT simultaneous same-capture reception
# (that is tested in test_same_capture_multisignal.py).
def test_zero_targets():
    loop = _run([], [2_399_000_000, 2_400_000_000, 2_401_000_000])
    assert loop.tracker.active_targets() == []
    assert loop.observations == []


def test_one_target():
    emitters = [Emitter(2_400_000_000, "QPSK")]
    loop = _run(emitters, [2_399_000_000, 2_400_000_000, 2_401_000_000])
    rep = score(_truth((1, 2_400_000_000, "QPSK", 0.0, math.inf)), loop.observations)
    assert rep.detection_rate == 1.0
    assert rep.missed_truth_ids == []
    assert loop.tracker.active_targets()[0].top3[0]["class_name"] == "QPSK"


def test_two_targets_frequency_separated_controlled_scheduling_fixture():
    """Two targets found ACROSS sequential LO dwells (controlled scheduling
    fixture), not a same-capture multi-signal claim."""
    emitters = [Emitter(2_400_000_000, "QPSK"), Emitter(2_400_250_000, "BPSK")]
    loop = _run(emitters, [2_399_750_000, 2_400_000_000, 2_400_250_000, 2_400_500_000])
    rep = score(_truth((1, 2_400_000_000, "QPSK", 0.0, math.inf),
                       (2, 2_400_250_000, "BPSK", 0.0, math.inf)), loop.observations)
    assert rep.detection_rate == 1.0
    assert rep.false_alarm_target_ids == []
    assert rep.detected_targets == 2


def test_three_targets_controlled_scheduling_fixture():
    """Three targets found ACROSS sequential LO dwells (controlled scheduling
    fixture), not a same-capture multi-signal claim."""
    emitters = [Emitter(2_400_000_000, "QPSK"), Emitter(2_400_250_000, "BPSK"),
                Emitter(2_399_750_000, "8PSK")]
    loop = _run(emitters, [2_399_750_000, 2_400_000_000, 2_400_250_000])
    rep = score(_truth((1, 2_400_000_000, "QPSK", 0.0, math.inf),
                       (2, 2_400_250_000, "BPSK", 0.0, math.inf),
                       (3, 2_399_750_000, "8PSK", 0.0, math.inf)), loop.observations)
    assert rep.detection_rate == 1.0
    assert rep.detected_targets == 3


# --- entry / exit ----------------------------------------------------------
def test_entry_and_exit_with_aging():
    # Target enters cycle 2 (t=2s) and leaves after cycle 4; aging drops it.
    truth = _truth((1, 2_400_000_000, "QPSK", 2.0, 4.0))
    radio = ReplayRadio([Emitter(2_400_000_000, "QPSK")])
    loop = MultiSignalScanLoop([2_399_000_000, 2_400_000_000, 2_401_000_000],
                               ScanLoopOptions(aging_cycles=3))
    detector = lambda raw: detect_public_training(np.asarray(raw), PUBLIC_TRAIN)  # noqa: E731
    for i in range(6):
        now = (i + 1) * 1.0
        # Emit only while the truth target is active (2 <= t < 4).
        if 2.0 <= now < 4.0:
            loop.sweep(detector, radio.tune, radio.capture, radio.flush, now)
            loop.classify_pass(_label_blind_classifier, radio.tune, radio.capture,
                               radio.flush, now)
        loop.end_cycle()
    rep = score(truth, loop.observations)
    assert rep.detection_rate == 1.0
    assert rep.first_discovery_seconds[1] == 0.0
    assert loop.tracker.active_targets() == []     # expired cleanup
    assert len(loop.tracker.history()) == 1


# --- range modification / cancel via the REAL Controller --------------------
def test_controller_range_modification_and_cancel():
    ctl = Controller(2_400_000_000, 2_395_000_000, 2_405_000_000, 1_000_000,
                     2_300_000_000, 2_500_000_000, max_points=101)

    class LoStub:
        def tune(self, hz): return int(hz)
        def flush(self): pass

    c = ctl.submit("SET_SCAN_RANGE_HZ 2399000000 2401000000 500000")
    ctl.drain(LoStub())
    assert c.response.startswith("OK")
    s = ctl.snapshot()
    assert (s["start_hz"], s["stop_hz"], s["step_hz"]) == (2_399_000_000, 2_401_000_000, 500_000)

    # Cancel a queued command before it is drained: it must be skipped.
    c2 = ctl.submit("SET_SCAN_RANGE_HZ 2390000000 2410000000 1000000")
    c2.cancelled = True
    ctl.drain(LoStub())
    s2 = ctl.snapshot()
    assert s2["start_hz"] == 2_399_000_000     # unchanged by the cancelled command


def test_adapter_range_modification_and_cancel():
    emitters = [Emitter(2_400_000_000, "QPSK")]
    radio = ReplayRadio(emitters)
    loop = MultiSignalScanLoop([2_399_000_000, 2_400_000_000, 2_401_000_000])
    detector = lambda raw: detect_public_training(np.asarray(raw), PUBLIC_TRAIN)  # noqa: E731

    # Range modification: new LO list is honoured.
    loop.apply_range([2_400_000_000])
    new_ids = loop.sweep(detector, radio.tune, radio.capture, radio.flush, 1.0)
    assert new_ids == [1]

    # Cancel: a sweep whose stop callback fires mid-way stops early and keeps what
    # it already has.  (Mirrors the real loop's ``stop.is_set()`` poll.)
    loop2 = MultiSignalScanLoop([2_399_000_000, 2_400_000_000, 2_401_000_000])
    radio2 = ReplayRadio(emitters, [2_399_000_000, 2_400_000_000, 2_401_000_000])
    calls = {"n": 0}

    def should_stop() -> bool:
        calls["n"] += 1
        return calls["n"] > 1                # stop after the first dwell

    ids = loop2.sweep(detector, radio2.tune, radio2.capture, radio2.flush, 1.0,
                      should_stop=should_stop)
    assert ids == []                          # no target at the first LO (2_399_000_000)
    assert calls["n"] == 2                    # polled at dwell 1 and dwell 2


# --- real UI event adapter per selected target (constellation not shared) ---
def _ui_for(loop, target_id):
    rec = [t for t in loop.tracker.active_targets() if t.target_id == target_id][0]
    # Per-target synthetic recovered IQ: the producer's tensor is a function of
    # the selected target's own centre, so two targets never share a constellation.
    rng = np.random.default_rng(int(rec.center_hz))
    tensor = np.zeros((8, 2, 1024), dtype=np.float32)
    tensor[:, 0, :] = 0.3 * rng.standard_normal((8, 1024))
    tensor[:, 1, :] = 0.2 * rng.standard_normal((8, 1024))
    arm = {"pred": 4, "mean_logits": [0.0] * 24, "finite": True}       # QPSK == index 4
    event = build_ui_event(1, arm, display_tensor=tensor)
    result = build_board_ui_result(event, center_hz=rec.center_hz, work_mode="BAND SCAN")
    return result


def test_real_ui_event_per_target_and_clear_on_switch():
    emitters = [Emitter(2_400_000_000, "QPSK"), Emitter(2_400_250_000, "BPSK")]
    loop = _run(emitters, [2_399_750_000, 2_400_000_000, 2_400_250_000, 2_400_500_000])
    ids = sorted(t.target_id for t in loop.tracker.active_targets())
    assert len(ids) == 2

    r1 = _ui_for(loop, ids[0])
    r2 = _ui_for(loop, ids[1])
    # Each selected target produces a valid, distinct result with its own centre.
    assert r1["measurements"]["spectrum_center_hz"] != r2["measurements"]["spectrum_center_hz"]
    assert r1["iq_valid"] and r2["iq_valid"]
    # Producer side never accumulates: each event carries exactly its own 512 IQ.
    assert r1["iq_i16_interleaved"] != r2["iq_i16_interleaved"]


# --- real recovery entry works offline (frozen recovery, unchanged) --------
def test_real_recovery_entry_offline():
    lo = 2_400_000_000
    raw = make_capture(lo, [Emitter(2_400_000_000, "QPSK", start=8192)])
    d = detect_public_training(raw, PUBLIC_TRAIN)
    assert d.score >= 0.10
    frame = recover_frame(raw, RECOVER)
    assert frame.tensor.shape == (8, 2, 1024)
    assert len(frame.tensor_sha256) == 64
    assert frame.metadata["cfo_hz"] == pytest.approx(0.0, abs=500.0)
