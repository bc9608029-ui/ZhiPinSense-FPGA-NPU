"""Injectable real-entry integration tests (C5).

These drive the FINAL patched loop -- ``integration/receiver_entry.ReceiverEntry``
-- directly with injected radio / infer / transport / controller stubs.  They do
NOT re-implement the receiver logic; the same class is what the board entry
(``standalone_receiver.multisignal.py``) wires real hardware into.

Chain covered: scan -> same-capture multi-candidate -> dedup -> per-target
tune/recover/classify -> event serialisation -> real UI parse/state ->
select/clear-old-IQ -> aging, plus range modify, cancel, disconnect, no-signal,
short frame, error recovery, same target across LO repeat, weak-target fairness.

The NPU ``infer`` is a LABEL-BLIND constant classifier (it never reads ground
truth); accuracy is not claimed here -- only the wiring is verified.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))
sys.path.insert(0, str(ROOT / "integration"))
sys.path.insert(0, str(ROOT))

from candidate_two_dc import train as PUBLIC_TRAIN, tail as PUBLIC_TAIL, recover as RECOVER  # noqa: E402
from receiver_core import CLASS_NAMES, recover_frame  # noqa: E402
from scan_runtime import detect_public_training  # noqa: E402
from standalone_control import Controller  # noqa: E402
from ui_event import build_board_ui_result, build_ui_event  # noqa: E402

from receiver_entry import EntryConfig, ReceiverEntry  # noqa: E402
from src.psd import pick_peaks  # noqa: E402
from src.ui_model import UiMultiSignalState  # noqa: E402

FS = 2_560_000
CAPTURE = 65_536


# --- synthetic emitter / capture (public-frame protocol) --------------------
@dataclass(eq=False)
class Emitter:
    center_hz: int
    class_name: str
    start: int = 8192
    amp: float = 1.0


def _payload() -> np.ndarray:
    rng = np.random.default_rng(7)
    return np.exp(1j * (np.pi / 4 + np.pi / 2 * rng.integers(0, 4, 1024))).astype(np.complex64)


def _frame(cfo_hz: float, amp: float = 1.0) -> np.ndarray:
    train = np.asarray(PUBLIC_TRAIN, dtype=np.complex128)
    tail = np.asarray(PUBLIC_TAIL, dtype=np.complex128)
    body = np.concatenate([np.zeros(2048), train, np.tile(_payload(), 8), tail, np.zeros(2048)])
    n = np.arange(body.size, dtype=np.float64)
    return amp * body * np.exp(2j * np.pi * float(cfo_hz) * n / FS)


def make_capture(lo_hz: int, emitters: list[Emitter], *,
                 noise_rms: float = 0.01, home_map: dict | None = None) -> np.ndarray:
    x = np.zeros(CAPTURE, dtype=np.complex128)
    for e in emitters:
        if home_map is not None and home_map[e] != int(lo_hz):
            continue
        cfo = float(e.center_hz - lo_hz)
        if abs(cfo) > 0.45 * FS:
            continue
        body = _frame(cfo, e.amp)
        stop = e.start + body.size
        if stop > CAPTURE:
            continue
        x[e.start:stop] += body
    if noise_rms > 0:
        rng = np.random.default_rng(123)
        x = x + noise_rms * (rng.standard_normal(CAPTURE) + 1j * rng.standard_normal(CAPTURE))
    return np.asarray(x, dtype=np.complex128)


class FakeRadio:
    """tune/flush/receive/close with pluggable capture behaviour."""

    def __init__(self, emitters=(), los=None, *, home: bool = True):
        self.emitters = list(emitters)
        self.los = list(los) if los else []
        self.home = home
        self.lo = 0
        self.tuned: list[int] = []
        self.fail_receive = False
        self.short_frame = False
        self.tone_buf: np.ndarray | None = None

    def tune(self, hz: int) -> int:
        self.lo = int(hz)
        self.tuned.append(self.lo)
        return self.lo

    def flush(self) -> None:
        pass

    def receive(self) -> np.ndarray:
        if self.fail_receive:
            raise RuntimeError("PLUTO_UNPLUGGED")
        if self.short_frame:
            return np.zeros(1024, dtype=np.complex128)
        if self.tone_buf is not None:
            return self.tone_buf
        home_map = None
        if self.home and self.emitters and self.los:
            home_map = {e: min(self.los, key=lambda l: abs(l - e.center_hz)) for e in self.emitters}
        return make_capture(self.lo, self.emitters, home_map=home_map)

    def close(self) -> list:
        return []


class FakeTransport:
    def __init__(self) -> None:
        self.events: list[dict] = []
        self.sent = 0
        self.failed = 0

    def send(self, event: dict) -> None:
        self.events.append(event)
        self.sent += 1


def _qpsk_infer(tensor):
    # Label-blind constant QPSK classifier (peaked logits at index 4).
    logits = [0.0] * 24
    logits[4] = 5.0
    return {"pred": 4, "mean_logits": logits}


def make_entry(radio, infer=None, controller=None, config=None,
               psd_detect=None):
    config = config or EntryConfig(scan_start_hz=2_400_000_000,
                                   scan_stop_hz=2_400_500_000,
                                   scan_step_hz=500_000,
                                   initial_mode="BAND_SCAN")
    if controller is not None and config.initial_mode == "BAND_SCAN":
        controller.update(mode="BAND_SCAN")
    transport = FakeTransport()
    entry = ReceiverEntry(
        radio=radio, infer=infer or _qpsk_infer, transport=transport,
        config=config,
        detector=lambda raw: detect_public_training(np.asarray(raw), PUBLIC_TRAIN),
        recover=recover_frame, recover_fn=RECOVER, class_names=list(CLASS_NAMES),
        ui_event_builder=build_ui_event, ui_result_builder=build_board_ui_result,
        controller=controller, psd_detect=psd_detect,
    )
    return entry, transport


def _targets_event(transport):
    return [e for e in transport.events if e.get("type") == "rml24_targets"]


# --- full chain: scan -> per-target classify -> event -> UI -> aging ---------
def test_full_chain_two_targets_events_and_serialization():
    los = [2_400_000_000, 2_400_500_000]
    emitters = [Emitter(2_400_000_000, "QPSK"), Emitter(2_400_500_000, "BPSK")]
    radio = FakeRadio(emitters, los)
    entry, transport = make_entry(radio)
    entry.step()                                   # cycle 1: sweep + classify + events
    targets = entry.scheduler.active_targets()
    assert len(targets) == 2

    # Per-target classification succeeded: both have a QPSK top1 (label-blind).
    for t in targets:
        assert t.status != "expired"
        assert t.top3 and t.top3[0]["class_name"] == "QPSK"
        assert t.confidence > 0.5

    # Real result events (one per classified target) carry the frozen schema
    # (build_board_ui_result validates internally), and their centres differ
    # (constellation never shared).
    results = [e for e in transport.events if e.get("type") == "result"]
    assert len(results) == 2
    for r in results:
        assert r["argmax_class"] == "QPSK"
        assert r["iq_valid"] is True
        assert r["measurements"]["spectrum_center_hz"] in (2_400_000_000, 2_400_500_000)
    assert results[0]["measurements"]["spectrum_center_hz"] != \
        results[1]["measurements"]["spectrum_center_hz"]

    # rml24_targets snapshot: correlation backend -> power_valid serialised null,
    # and the whole event is standard JSON (no NaN reaches the wire).
    tev = _targets_event(transport)[-1]
    assert tev["targets"][0]["power_valid"] is None     # unmeasured -> null, never NaN
    assert tev["targets"][0]["top3"][0]["class_name"] == "QPSK"
    assert "NaN" not in json.dumps(tev)

    # Aging: remove both emitters; after 3 miss cycles both expire.
    radio.emitters = []
    for _ in range(3):
        entry.step()
    assert entry.scheduler.active_targets() == []
    assert len(entry.scheduler.tracker.history()) == 2


# --- real UI parse/state: select + clear old IQ -----------------------------
def test_ui_state_select_and_clear_old_iq():
    los = [2_400_000_000, 2_400_500_000]
    emitters = [Emitter(2_400_000_000, "QPSK"), Emitter(2_400_500_000, "BPSK")]
    radio = FakeRadio(emitters, los)
    entry, _ = make_entry(radio)
    entry.step()
    recs = entry.scheduler.active_targets()

    ui = UiMultiSignalState.empty()
    ui.refresh(recs, None)
    assert len(ui.targets) == 2

    iq1 = np.arange(512, dtype=np.complex128)
    ui.select(recs[0].target_id, iq1)
    assert ui.selected_target_id == recs[0].target_id
    assert ui.constellation_iq is not None and ui.constellation_iq.shape == (512,)

    # Switching targets replaces (clears) the old constellation, never accumulates.
    iq2 = np.arange(512, 512 + 512, dtype=np.complex128)
    ui.select(recs[1].target_id, iq2)
    assert ui.selected_target_id == recs[1].target_id
    assert np.allclose(ui.constellation_iq, iq2)
    assert not np.allclose(ui.constellation_iq, iq1)

    ui.clear_constellation()
    assert ui.constellation_iq is None

    # A vanished selection falls back to none and clears the constellation.
    ui.select(recs[0].target_id, iq1)
    ui.refresh([], None)
    assert ui.selected_target_id is None
    assert ui.constellation_iq is None


# --- same-capture multi-candidate (PSD) -> unclassified (no fabricated Top3) -
def _tones(offsets_amp: list[tuple[int, float]], n: int = 4096) -> np.ndarray:
    x = np.zeros(n, dtype=np.complex128)
    for off, amp in offsets_amp:
        x += amp * np.exp(2j * np.pi * off * np.arange(n) / FS)
    return x


def test_same_capture_psd_multi_candidate_and_unclassified():
    radio = FakeRadio([], home=True)
    radio.tone_buf = _tones([(-50_000, 1.0), (0.0, 1.0), (+50_000, 1.0)])
    # Single LO dwell: the three tones are candidates from ONE capture.
    entry, transport = make_entry(radio, psd_detect=pick_peaks, config=EntryConfig(
        scan_start_hz=2_400_000_000, scan_stop_hz=2_400_000_000,
        scan_step_hz=1_000_000, initial_mode="BAND_SCAN"))
    entry.step()
    targets = entry.scheduler.active_targets()
    assert len(targets) == 3                       # THREE candidates from ONE capture

    tev = _targets_event(transport)[-1]
    for t in tev["targets"]:
        assert t["power_valid"] is not None and t["power_valid"] >= 14.0  # numeric PSD power
        # Tone targets have no recoverable public frame -> UNCLASSIFIED with no
        # fabricated Top3/confidence (the honest "未分类" outcome).
        assert t["top3"] == []
        assert t["confidence"] == 0.0


# --- dedup: same target observed across two LO dwells -----------------------
def test_same_target_across_lo_dedup():
    los = [2_400_000_000, 2_400_500_000]
    # All-visible (no home_map): the one emitter is in-band at BOTH LOs, so both
    # dwells detect it at the same absolute centre -> one deduped target.
    radio = FakeRadio([Emitter(2_400_250_000, "QPSK")], los, home=False)
    entry, _ = make_entry(radio)
    entry.step()
    targets = entry.scheduler.active_targets()
    assert len(targets) == 1
    assert abs(targets[0].center_hz - 2_400_250_000) < 6_250


# --- no-signal / short frame / disconnect / error recovery ------------------
def test_no_signal_empty_target_list():
    radio = FakeRadio([], [2_400_000_000, 2_400_500_000])
    entry, transport = make_entry(radio)
    entry.step()
    assert entry.scheduler.active_targets() == []
    tev = _targets_event(transport)[-1]
    assert tev["targets"] == []
    states = [e for e in transport.events if e.get("type") == "state"]
    assert states[-1]["presence_state"] == "NO_SIGNAL"


def test_short_frame_survives():
    radio = FakeRadio([Emitter(2_400_000_000, "QPSK")], [2_400_000_000])
    radio.short_frame = True
    entry, _ = make_entry(radio)
    status = entry.step()                          # must not raise
    assert entry.scheduler.active_targets() == []  # detector rejected the short dwell
    assert status["state"] == "SCANNED"


def test_disconnect_survives_and_recovers():
    los = [2_400_000_000, 2_400_500_000]
    radio = FakeRadio([Emitter(2_400_000_000, "QPSK")], los)
    entry, _ = make_entry(radio)
    radio.fail_receive = True
    entry.step()                                   # disconnected: no crash
    assert entry.disconnects > 0
    assert entry.scheduler.active_targets() == []
    # Reconnect: the loop recovers and finds the target on the next frame.
    radio.fail_receive = False
    entry.step()
    assert len(entry.scheduler.active_targets()) == 1


def test_error_recovery_infer_failure_continues():
    los = [2_400_000_000, 2_400_500_000]
    emitters = [Emitter(2_400_000_000, "QPSK"), Emitter(2_400_500_000, "BPSK")]
    radio = FakeRadio(emitters, los)
    calls = {"n": 0}

    def flaky_infer(tensor):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("NPU_SOCKET_LOST")
        return _qpsk_infer(tensor)

    entry, _ = make_entry(radio, infer=flaky_infer)
    entry.step()
    # One target's infer failed (rejected/unclassified), the other classified.
    assert entry.rejected >= 1
    assert entry.valid >= 1
    tops = {t.target_id: (t.top3[0]["class_name"] if t.top3 else None)
            for t in entry.scheduler.active_targets()}
    assert set(tops.values()) == {"QPSK", None}     # failed one stays unclassified


# --- range modify / cancel via the REAL Controller --------------------------
def test_range_modification_cleans_up_targets():
    ctl = Controller(2_400_000_000, 2_400_000_000, 2_400_500_000, 500_000,
                     2_300_000_000, 2_500_000_000, max_points=101)
    ctl.update(mode="BAND_SCAN")
    radio = FakeRadio([Emitter(2_400_000_000, "QPSK")],
                      [2_400_000_000, 2_400_500_000])
    entry, _ = make_entry(radio, controller=ctl)
    entry.step()
    assert len(entry.scheduler.active_targets()) == 1

    # New range that excludes the 2_400_000_000 target -> apply_range drops it.
    ctl.submit("SET_SCAN_RANGE_HZ 2400500000 2401000000 500000")
    entry.step()                                   # drains -> RESTART + cleanup
    assert entry.scheduler.active_targets() == []
    assert entry.scheduler.removed_log()[0]["reason"] == "outside_new_band"
    assert entry.scheduler.lo_points == [2_400_500_000, 2_401_000_000]


def test_cancel_command_skipped():
    ctl = Controller(2_400_000_000, 2_400_000_000, 2_400_500_000, 500_000,
                     2_300_000_000, 2_500_000_000, max_points=101)
    ctl.update(mode="BAND_SCAN")
    radio = FakeRadio([], [2_400_000_000, 2_400_500_000])
    entry, _ = make_entry(radio, controller=ctl)
    c = ctl.submit("SET_SCAN_RANGE_HZ 2400000000 2410000000 1000000")
    c.cancelled = True
    entry.step()                                   # drain skips the cancelled command
    s = ctl.snapshot()
    assert s["stop_hz"] == 2_400_500_000            # unchanged
    assert entry.scheduler.lo_points == [2_400_000_000, 2_400_500_000]


# --- weak-target fairness (no strong-signal monopoly) -----------------------
def test_weak_target_fairness():
    from src.scan_adapter import ScanLoopOptions
    los = [2_400_000_000, 2_400_500_000]
    emitters = [Emitter(2_400_000_000, "QPSK", amp=1.0),      # strong
                Emitter(2_400_500_000, "BPSK", amp=0.25)]     # weak (12 dB down, still recoverable)
    radio = FakeRadio(emitters, los)
    entry, _ = make_entry(radio, config=EntryConfig(
        scan_start_hz=2_400_000_000, scan_stop_hz=2_400_500_000, scan_step_hz=500_000,
        initial_mode="BAND_SCAN", scheduler=ScanLoopOptions(classify_budget=1)))
    for _ in range(3):                             # budget 1 -> one classification/cycle
        entry.step()
    tops = {t.target_id: (t.top3[0]["class_name"] if t.top3 else None)
            for t in entry.scheduler.active_targets()}
    # Both the strong AND the weak target get classified: no monopoly.
    assert set(tops.values()) == {"QPSK"}


# --- FIXED mode keeps the original single-result behaviour ------------------
def test_fixed_mode_unchanged():
    radio = FakeRadio([Emitter(2_400_000_000, "QPSK")], home=False)
    entry, transport = make_entry(radio, config=EntryConfig(
        fixed_center_hz=2_400_000_000, initial_mode="FIXED"))
    status = entry.step()
    assert status["state"] == "IDENTIFIED"
    results = [e for e in transport.events if e.get("type") == "result"]
    assert len(results) == 1
    assert not _targets_event(transport)           # no multi-target list in FIXED
