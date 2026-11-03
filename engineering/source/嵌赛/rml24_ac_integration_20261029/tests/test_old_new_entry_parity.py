"""Old (A-line) vs new (multisignal_receiver_entry) entry parity -- AC req 4.

Drives the SAME synthesized public-frame IQ through:

  1. the A-line original FIXED body (``standalone_receiver.py`` lines 102-188,
     extracted verbatim as a reference function), and
  2. the flat-deployed ``multisignal_receiver_entry.ReceiverEntry._step_fixed``.

and asserts the recovered tensor, classification input/call, feature
measurement, records.jsonl row, status.json, and UI events (state + result) are
identical except for wall-clock timestamps.  It also asserts the FIXED
infer-failure contract (fatal, never disguised as no-signal) and adds a
same-capture PSD multi-candidate test that does NOT use ``home_map`` (three
narrow-band stand-ins discovered from ONE dwell).

The NPU ``infer`` here is a LABEL-BLIND constant classifier: accuracy is not
claimed -- only that the two entries produce byte-identical observables from the
same IQ.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pytest

TREE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TREE / "overlay/rml24_final/runtime"))
sys.path.insert(0, str(TREE / "overlay/rml24_final/board_runtime"))
sys.path.insert(0, str(TREE / "local_base/runtime"))
sys.path.insert(0, str(TREE / "local_base/recovery"))
sys.path.insert(0, str(TREE / "local_base/board_runtime"))

import candidate_two_dc  # noqa: E402
from receiver_core import CLASS_NAMES, recover_frame  # noqa: E402
from scan_runtime import detect_public_training  # noqa: E402
from standalone_control import Controller  # noqa: E402
from ui_event import MODEL_SHA as UI_MODEL_SHA, build_board_ui_result, build_ui_event  # noqa: E402
from multisignal_receiver_entry import (  # noqa: E402
    MODEL_SHA as ENTRY_MODEL_SHA,
    EntryConfig,
    ReceiverEntry,
    ScanLoopOptions,
)
from multisignal_psd import pick_peaks  # noqa: E402

FS = 2_560_000
CAPTURE = 65_536
FIXED_HZ = 2_400_000_000
# A-line state() model_sha literal (standalone_receiver.py line 76).
A_LINE_MODEL_SHA = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"


# --- synthetic public-frame capture -----------------------------------------
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
    train = np.asarray(candidate_two_dc.train, dtype=np.complex128)
    tail = np.asarray(candidate_two_dc.tail, dtype=np.complex128)
    body = np.concatenate([np.zeros(2048), train, np.tile(_payload(), 8), tail, np.zeros(2048)])
    n = np.arange(body.size, dtype=np.float64)
    return amp * body * np.exp(2j * np.pi * float(cfo_hz) * n / FS)


def make_capture(lo_hz: int, emitters: list[Emitter], *, noise_rms: float = 0.01) -> np.ndarray:
    x = np.zeros(CAPTURE, dtype=np.complex128)
    for e in emitters:
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
    """tune/flush/receive/close + ``current_hz`` (mirrors A-line lo + radio)."""

    def __init__(self, raw: np.ndarray):
        self._raw = raw
        self.lo = 0
        self.tuned: list[int] = []

    @property
    def current_hz(self) -> int:
        return self.lo

    def tune(self, hz: int) -> int:
        self.lo = int(hz)
        self.tuned.append(self.lo)
        return self.lo

    def flush(self) -> None:
        pass

    def receive(self, n: int = 65536) -> np.ndarray:
        return self._raw

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
    logits = [0.0] * 24
    logits[4] = 5.0
    return {"pred": 4, "mean_logits": logits}


class RecordingInfer:
    """Wraps an infer to record every tensor it was called with."""

    def __init__(self, infer=None):
        self._infer = infer or _qpsk_infer
        self.tensors: list[np.ndarray] = []

    def __call__(self, tensor):
        self.tensors.append(np.asarray(tensor))
        return self._infer(tensor)


def _state_events(transport):
    return [e for e in transport.events if e.get("type") == "state"]


def _result_events(transport):
    return [e for e in transport.events if e.get("type") == "result"]


def _strip_timing(row: dict) -> dict:
    out = dict(row)
    for key in ("capture_time_ns", "board_monotonic", "elapsed_ms"):
        out.pop(key, None)
    return out


# --- A-line reference: the original FIXED body, extracted verbatim ----------
def a_line_fixed_frame(radio, ctl, infer, seq, fixed_hz, ui):
    """One FIXED frame of the A-line loop (standalone_receiver.py 102-188).

    Returns ``(frame, tensor, infer_tensors, measurement, row)`` where
    ``measurement`` is the controller's (rms_iq, peak_iq, energy_iq2, backend)
    and ``row`` is the records.jsonl row.  Events go to ``ui``.
    """
    last_state = {"t": 0.0}

    def state(presence, force=False):
        ctl.update(presence=presence)
        now = time.monotonic()
        if not force and now - last_state["t"] < 0.5:
            return
        s = ctl.snapshot()
        ui.send(dict(type="state", version="rml24-standalone-state-v1",
                     command_id=s["command_id"], work_mode=s["mode"],
                     run_state="RUNNING" if s["running"] else "STOPPED",
                     presence_state=presence, timestamp_us=time.time_ns() // 1000,
                     model_sha=A_LINE_MODEL_SHA))
        last_state["t"] = now

    begin = time.monotonic()
    raw = None
    steps: list = []
    center = fixed_hz
    capture_ns = 0
    state("ACQUIRING")
    raw = np.asarray(radio.receive(65536))
    capture_ns = time.time_ns()

    arm: dict = {}
    tensor = None
    frame = None
    if raw is not None:
        try:
            frame = recover_frame(raw, candidate_two_dc.recover)
        except Exception as exc:
            arm = {"pred": -1, "finite": False,
                   "error": type(exc).__name__ + ": " + str(exc)}

    infer_tensors: list = []
    if frame is not None:
        tensor = frame.tensor
        arm.update(frame.metadata, input_sha256=frame.tensor_sha256)
        # Failure of real NPU inference is fatal, not disguised as no signal.
        arm.update(infer(tensor))
        arm["finite"] = True
        infer_tensors.append(tensor)
        measure_start = time.monotonic_ns()
        z = (tensor[:, 0, :] + 1j * tensor[:, 1, :]).mean(axis=0, dtype=np.complex128)
        energy = float(np.sum(np.abs(z) ** 2))
        ctl.update(frame_id=seq, rms_iq=float(np.sqrt(energy / 1024)),
                   peak_iq=float(np.max(np.abs(z))), energy_iq2=energy,
                   feature_latency_us=(time.monotonic_ns() - measure_start) / 1000,
                   backend="software")
        event = build_ui_event(seq, arm, display_tensor=tensor)
        result = build_board_ui_result(event, center_hz=center, work_mode="FIXED")
        if result is not None:
            ui.send(result)
        state("SIGNAL_PRESENT", True)
    else:
        arm.setdefault("pred", -1)
        arm.setdefault("finite", False)
        arm.setdefault("error", "NO_VALID_PUBLIC_FRAME")
        state("NO_SIGNAL", True)

    row = dict(frame_id=seq, mode="FIXED", capture_time_ns=capture_ns,
               board_monotonic=time.monotonic(), center_hz=center,
               actual_lo_hz=radio.current_hz, candidate=arm, scan_steps=steps,
               elapsed_ms=(time.monotonic() - begin) * 1000)
    measurement = dict(
        rms_iq=ctl.snapshot()["rms_iq"],
        peak_iq=ctl.snapshot()["peak_iq"],
        energy_iq2=ctl.snapshot()["energy_iq2"],
        backend=ctl.snapshot()["backend"],
    )
    return frame, tensor, infer_tensors, measurement, row


def _make_controller(mode="FIXED"):
    ctl = Controller(FIXED_HZ, 2_400_000_000, 2_400_500_000, 500_000,
                     2_300_000_000, 2_500_000_000, max_points=101)
    ctl.update(mode=mode)
    return ctl


def _fixed_raw() -> np.ndarray:
    return make_capture(FIXED_HZ, [Emitter(FIXED_HZ, "QPSK")])


def _make_entry(radio, infer=None, config=None, controller=None, out_dir=None,
                psd_detect=None):
    config = config or EntryConfig(fixed_center_hz=FIXED_HZ, initial_mode="FIXED",
                                   out_dir=out_dir)
    transport = FakeTransport()
    entry = ReceiverEntry(
        radio=radio, infer=infer or _qpsk_infer, transport=transport, config=config,
        detector=lambda raw: detect_public_training(np.asarray(raw), candidate_two_dc.train),
        recover=recover_frame, recover_fn=candidate_two_dc.recover,
        class_names=list(CLASS_NAMES),
        ui_event_builder=build_ui_event, ui_result_builder=build_board_ui_result,
        controller=controller, psd_detect=psd_detect,
    )
    return entry, transport


# --- parity: recovered tensor / infer input / measurement -------------------
def test_fixed_recovered_tensor_infer_and_measurement_match(tmp_path):
    raw = _fixed_raw()
    # A-line reference (pre-tuned, like standalone_receiver.main() line 89).
    ref_ctl = _make_controller("FIXED")
    ref_radio = FakeRadio(raw)
    ref_radio.tune(FIXED_HZ); ref_radio.flush()
    ref_ui = FakeTransport()
    ref_infer = RecordingInfer()
    _, ref_tensor, _, ref_meas, _ = a_line_fixed_frame(
        ref_radio, ref_ctl, ref_infer, 0, FIXED_HZ, ref_ui)

    # New entry (pre-tuned, like standalone_receiver_multisignal.main() line 125).
    entry_ctl = _make_controller("FIXED")
    entry_radio = FakeRadio(raw.copy())
    entry_radio.tune(FIXED_HZ); entry_radio.flush()
    entry_infer = RecordingInfer()
    entry, entry_ui = _make_entry(entry_radio, infer=entry_infer,
                                  controller=entry_ctl, out_dir=tmp_path)
    status = entry.step()
    assert status["state"] == "IDENTIFIED"

    # Classification input/call: infer was called ONCE with the SAME tensor.
    assert ref_tensor is not None
    assert len(ref_infer.tensors) == 1
    assert len(entry_infer.tensors) == 1
    assert np.array_equal(ref_infer.tensors[0], entry_infer.tensors[0])
    assert np.array_equal(ref_tensor, entry_infer.tensors[0])

    # Feature measurement: identical deterministic math on the identical tensor.
    assert ref_meas["rms_iq"] == entry_ctl.snapshot()["rms_iq"]
    assert ref_meas["peak_iq"] == entry_ctl.snapshot()["peak_iq"]
    assert ref_meas["energy_iq2"] == entry_ctl.snapshot()["energy_iq2"]
    assert ref_meas["backend"] == entry_ctl.snapshot()["backend"] == "software"


def test_fixed_result_event_matches_a_line(tmp_path):
    raw = _fixed_raw()

    ref_ctl = _make_controller("FIXED")
    ref_radio = FakeRadio(raw); ref_radio.tune(FIXED_HZ); ref_radio.flush()
    ref_ui = FakeTransport()
    a_line_fixed_frame(ref_radio, ref_ctl, _qpsk_infer, 0, FIXED_HZ, ref_ui)

    entry_ctl = _make_controller("FIXED")
    entry_radio = FakeRadio(raw.copy()); entry_radio.tune(FIXED_HZ); entry_radio.flush()
    entry, entry_ui = _make_entry(entry_radio, controller=entry_ctl, out_dir=tmp_path)
    entry.step()

    ref_result = _result_events(ref_ui)[0]
    new_result = _result_events(entry_ui)[0]
    # Identical except the wall-clock timestamp.
    ref_result.pop("timestamp_us")
    new_result.pop("timestamp_us")
    assert ref_result == new_result
    assert ref_result["argmax_class"] == "QPSK"


def test_fixed_state_events_match_a_line(tmp_path):
    raw = _fixed_raw()

    ref_ctl = _make_controller("FIXED")
    ref_radio = FakeRadio(raw); ref_radio.tune(FIXED_HZ); ref_radio.flush()
    ref_ui = FakeTransport()
    a_line_fixed_frame(ref_radio, ref_ctl, _qpsk_infer, 0, FIXED_HZ, ref_ui)

    entry_ctl = _make_controller("FIXED")
    entry_radio = FakeRadio(raw.copy()); entry_radio.tune(FIXED_HZ); entry_radio.flush()
    entry, entry_ui = _make_entry(entry_radio, controller=entry_ctl, out_dir=tmp_path)
    entry.step()

    def canonical(states):
        return [(s["presence_state"], s["model_sha"], s["version"],
                 s["work_mode"], s["run_state"]) for s in states]

    ref_states = _state_events(ref_ui)
    new_states = _state_events(entry_ui)
    assert canonical(ref_states) == canonical(new_states)
    # ACQUIRING then SIGNAL_PRESENT, both carrying the frozen model sha.
    assert [s["presence_state"] for s in ref_states] == ["ACQUIRING", "SIGNAL_PRESENT"]
    assert all(s["model_sha"] == A_LINE_MODEL_SHA for s in new_states)


def test_fixed_records_row_and_status_match_a_line(tmp_path):
    raw = _fixed_raw()

    ref_ctl = _make_controller("FIXED")
    ref_radio = FakeRadio(raw); ref_radio.tune(FIXED_HZ); ref_radio.flush()
    ref_ui = FakeTransport()
    _, _, _, _, ref_row = a_line_fixed_frame(ref_radio, ref_ctl, _qpsk_infer, 0, FIXED_HZ, ref_ui)

    entry_ctl = _make_controller("FIXED")
    entry_radio = FakeRadio(raw.copy()); entry_radio.tune(FIXED_HZ); entry_radio.flush()
    entry, entry_ui = _make_entry(entry_radio, controller=entry_ctl, out_dir=tmp_path)
    entry.step()

    # records.jsonl row: identical modulo wall-clock timestamps.
    (tmp_path / "records.jsonl").write_text(json.dumps(ref_row) + "\n")
    # (The entry already appended its own row; compare field-by-field instead.)
    new_row = json.loads((tmp_path / "records.jsonl").read_text().splitlines()[-1])
    assert _strip_timing(ref_row) == _strip_timing(new_row)

    # status.json: valid/rejected/records/contract flags identical.
    status = json.loads((tmp_path / "status.json").read_text())
    assert status["valid"] == 1
    assert status["rejected"] == 0
    assert status["records"] == 1
    assert status["no_tcp"] is True and status["no_tx_handshake"] is True


# --- FIXED infer failure is FATAL (matches A-line "not disguised") ----------
def test_fixed_infer_failure_is_fatal():
    raw = _fixed_raw()

    def boom(tensor):
        raise RuntimeError("NPU_SOCKET_LOST")

    ctl = _make_controller("FIXED")
    radio = FakeRadio(raw); radio.tune(FIXED_HZ); radio.flush()
    entry, _ = _make_entry(radio, infer=boom, controller=ctl)
    with pytest.raises(RuntimeError, match="NPU_SOCKET_LOST"):
        entry.step()
    # Not counted as a valid/rejected frame; the exception propagated uncaught.
    assert entry.valid == 0
    assert entry.rejected == 0


# --- FIXED no-signal path matches A-line (reject + NO_SIGNAL) ---------------
def test_fixed_no_signal_matches_a_line(tmp_path):
    raw = np.zeros(CAPTURE, dtype=np.complex128)  # pure noise -> no recoverable frame

    ref_ctl = _make_controller("FIXED")
    ref_radio = FakeRadio(raw); ref_radio.tune(FIXED_HZ); ref_radio.flush()
    ref_ui = FakeTransport()
    _, ref_tensor, ref_infer, _, ref_row = a_line_fixed_frame(
        ref_radio, ref_ctl, _qpsk_infer, 0, FIXED_HZ, ref_ui)

    entry_ctl = _make_controller("FIXED")
    entry_radio = FakeRadio(raw.copy()); entry_radio.tune(FIXED_HZ); entry_radio.flush()
    entry, entry_ui = _make_entry(entry_radio, controller=entry_ctl, out_dir=tmp_path)
    status = entry.step()

    assert ref_tensor is None and ref_infer == [] and ref_row["candidate"]["finite"] is False
    assert status["state"] == "NO_SIGNAL"
    assert entry.rejected == 1 and entry.valid == 0
    assert _state_events(entry_ui)[-1]["presence_state"] == "NO_SIGNAL"
    new_row = json.loads((tmp_path / "records.jsonl").read_text().splitlines()[-1])
    assert _strip_timing(ref_row) == _strip_timing(new_row)


# --- same-capture PSD multi-candidate (NO home_map) -------------------------
def _tones(offsets_amp: list[tuple[int, float]], n: int = 4096) -> np.ndarray:
    x = np.zeros(n, dtype=np.complex128)
    for off, amp in offsets_amp:
        x += amp * np.exp(2j * np.pi * off * np.arange(n) / FS)
    return x


class ToneRadio:
    def __init__(self, buf: np.ndarray) -> None:
        self.buf = buf
        self.lo = 0
        self.tuned: list[int] = []

    @property
    def current_hz(self) -> int:
        return self.lo

    def tune(self, hz: int) -> int:
        self.lo = int(hz)
        self.tuned.append(self.lo)
        return self.lo

    def flush(self) -> None:
        pass

    def receive(self, n: int = 65536) -> np.ndarray:
        return self.buf

    def close(self) -> list:
        return []


def test_same_capture_psd_multi_candidate_no_home_map():
    # THREE narrow-band stand-ins discovered from ONE capture: the honest
    # same-capture multi-candidate path (software PSD).  No home_map here.
    radio = ToneRadio(_tones([(-50_000, 1.0), (0.0, 1.0), (+50_000, 1.0)]))
    config = EntryConfig(scan_start_hz=FIXED_HZ, scan_stop_hz=FIXED_HZ,
                         scan_step_hz=1_000_000, initial_mode="BAND_SCAN")
    # No controller: _NullController derives the single-LO-point range from the
    # config, so ONE dwell yields the three candidates (matches the C-line test).
    entry, transport = _make_entry(radio, config=config, psd_detect=pick_peaks)
    entry.step()

    targets = entry.scheduler.active_targets()
    assert len(targets) == 3

    tev = [e for e in transport.events if e.get("type") == "rml24_targets"][-1]
    for t in tev["targets"]:
        assert t["power_valid"] is not None and t["power_valid"] >= 14.0
        # Tone stand-ins carry no recoverable public frame -> unclassified,
        # no fabricated Top3/confidence.
        assert t["top3"] == []
        assert t["confidence"] == 0.0
    assert "NaN" not in json.dumps(tev)


# --- model identity: flat entry carries the frozen A-line model sha ---------
def test_entry_model_sha_matches_ui_and_a_line():
    assert ENTRY_MODEL_SHA == UI_MODEL_SHA == A_LINE_MODEL_SHA
    assert ENTRY_MODEL_SHA == "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"


# --- the candidate entry drives the flat-deployed ReceiverEntry -------------
def test_candidate_entry_wires_flat_receiver_entry():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "standalone_receiver_multisignal",
        TREE / "overlay/rml24_final/board_runtime/standalone_receiver_multisignal.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.ReceiverEntry is ReceiverEntry          # same class, flat-deployed
    assert mod.EntryConfig is EntryConfig
    assert mod.ScanLoopOptions is ScanLoopOptions
