"""Injectable receiver entry (C5): the FINAL patched scan/recover/classify loop.

This is the ONE loop the board entry (``standalone_receiver.multisignal.py``)
and the offline integration tests both execute -- the test does NOT re-implement
the receiver logic.  Every board dependency is constructor-injected:

* ``radio``      : tune(hz)->actual, flush(), receive()->raw, close()
* ``infer``      : infer(tensor)->arm dict (NPU; stub in tests, label-blind)
* ``transport``  : .send(event), .sent/.failed counters (UI socket stand-in)
* ``clock``      : seconds source (time.monotonic)
* ``detector``   : detect(raw)->PublicDetection (scan_runtime.detect_public_training)
* ``recover``    : recover_frame(raw, recover_fn)->frame | None
* ``controller`` : standalone_control.Controller (real or a test shim)

Loop semantics (mirrors the patched standalone_receiver, plus the C3 scheduler):

* FIXED mode keeps the original single-result behaviour (no target list).
* BAND_SCAN mode drives the fair scheduler: periodic full-band rescan
  (correlation sweep or software PSD multi-candidate sweep), round-robin
  per-target tune/recover/classify/event, fair revisit, then aging.  A
  ``rml24_targets`` snapshot event is emitted every frame for the five-page UI.
* Detector/capture/recover/infer failures are recorded (pred=-1, finite=False)
  and the loop continues -- never a crash; this is the "error recovery" path.
* Band-change cleanup/migration is delegated to ``scheduler.apply_range`` so the
  target list survives a range modification deterministically.
"""

from __future__ import annotations

import json
import math
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

try:  # flat deployment (board runtime)
    from multisignal_scan_adapter import MultiSignalScanLoop, ScanLoopOptions  # type: ignore
except ImportError:  # C-line dev tree
    from src.scan_adapter import MultiSignalScanLoop, ScanLoopOptions  # type: ignore


CAPTURE_SAMPLES = 65_536
STATE_VERSION = "rml24-standalone-state-v1"


class _NoDet:
    """Sentinel for a detector that failed (short frame, non-finite IQ, ...)."""

    def __init__(self) -> None:
        self.score = -1.0
        self.coarse_cfo_hz = 0.0


@dataclass
class EntryConfig:
    fixed_center_hz: int = 2_400_000_000
    scan_start_hz: int = 2_395_000_000
    scan_stop_hz: int = 2_405_000_000
    scan_step_hz: int = 1_000_000
    initial_mode: str = "FIXED"                  # FIXED | BAND_SCAN
    duration_sec: float = 0.0
    save_captures: bool = False
    out_dir: Path | None = None
    scheduler: ScanLoopOptions | None = None     # defaults to ScanLoopOptions()


class _NullController:
    """Minimal always-running controller when none is injected."""

    def __init__(self, cfg: EntryConfig) -> None:
        self.mode = cfg.initial_mode
        self.running = True
        self.start_hz = cfg.scan_start_hz
        self.stop_hz = cfg.scan_stop_hz
        self.step_hz = cfg.scan_step_hz
        self.fixed_hz = cfg.fixed_center_hz
        self.command_id = 0

    def snapshot(self) -> dict[str, Any]:
        return {"mode": self.mode, "running": self.running,
                "start_hz": self.start_hz, "stop_hz": self.stop_hz,
                "step_hz": self.step_hz, "fixed_hz": self.fixed_hz,
                "command_id": self.command_id}

    def drain(self, lo) -> bool:
        return False


class ReceiverEntry:
    def __init__(
        self,
        *,
        radio: Any,
        infer: Callable[[np.ndarray], dict[str, Any]],
        transport: Any,
        config: EntryConfig,
        detector: Callable[[np.ndarray], Any],
        recover: Callable[[np.ndarray, Any], Any],
        recover_fn: Any,
        class_names: list[str],
        ui_event_builder: Callable[..., dict[str, Any]],
        ui_result_builder: Callable[..., dict[str, Any] | None],
        controller: Any | None = None,
        psd_detect: Callable[[int, np.ndarray], list[Any]] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.radio = radio
        self.infer = infer
        self.transport = transport
        self.cfg = config
        self.detector = detector
        self.recover = recover
        self.recover_fn = recover_fn
        self.class_names = class_names
        self.build_ui_event = ui_event_builder
        self.build_board_ui_result = ui_result_builder
        self.psd_detect = psd_detect
        self.clock = clock
        self.ctl = controller if controller is not None else _NullController(config)
        self.stop = threading.Event()
        self.started = self.clock()
        self.seq = 0
        self.valid = 0
        self.rejected = 0
        self.disconnects = 0
        self.cycle = 0
        self.last_presence: str | None = None
        self.last_event: dict[str, Any] | None = None
        self.scheduler = MultiSignalScanLoop(
            self._lo_points(), config.scheduler or ScanLoopOptions()
        )

    # -- helpers -------------------------------------------------------------
    def _lo_points(self) -> list[int]:
        s = self.ctl.snapshot()
        start, stop, step = int(s["start_hz"]), int(s["stop_hz"]), int(s["step_hz"])
        pts: list[int] = []
        hz = start
        while hz <= stop:
            pts.append(hz)
            hz += step
        if not pts:
            pts = [start]
        return pts

    def work_mode(self) -> str:
        return "BAND SCAN" if self.ctl.snapshot()["mode"] == "BAND_SCAN" else "FIXED"

    def _emit(self, event: dict[str, Any]) -> None:
        self.transport.send(event)

    def _json_safe_targets(self, snapshot: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """JSON-safe target records: unmeasured power (internal NaN) -> null.

        ``power_valid`` is NaN internally when the correlation detector (no PSD)
        produced the target.  NaN is NOT standard JSON, so the wire format for
        the C++ list page serialises it as ``null``; numeric PSD measurements
        stay numeric.  This is the frozen serialisation rule for C2/C5.
        """
        out: list[dict[str, Any]] = []
        for t in snapshot:
            d = dict(t)
            pv = d.get("power_valid")
            if isinstance(pv, float) and math.isnan(pv):
                d["power_valid"] = None
            out.append(d)
        return out

    def _safe_detect(self, raw: np.ndarray) -> Any:
        """Detector with error recovery: short frame / non-finite -> _NoDet."""
        try:
            return self.detector(np.asarray(raw))
        except Exception:
            return _NoDet()

    def _capture(self) -> np.ndarray:
        """Capture with error recovery: a dropped radio yields a no-signal dwell."""
        try:
            return np.asarray(self.radio.receive(), dtype=np.complex128)
        except Exception:
            self.disconnects += 1
            return np.zeros(CAPTURE_SAMPLES, dtype=np.complex128)

    def _top3(self, arm: dict[str, Any]) -> tuple[list[dict[str, Any]], float]:
        pred = arm.get("pred", -1)
        if not isinstance(pred, int) or not (0 <= pred < len(self.class_names)):
            return [], 0.0
        logits = arm.get("logits") or arm.get("mean_logits")
        if isinstance(logits, list) and len(logits) == len(self.class_names):
            v = np.asarray(logits, dtype=np.float64)
            if np.isfinite(v).all():
                w = np.exp(v - v.max())
                p = w / w.sum()
                order = np.argsort(v)[::-1][:3]
                top3 = [{"class_name": self.class_names[int(i)],
                         "confidence": float(p[int(i)])} for i in order]
                return top3, float(p[pred])
        return [], 0.0

    def _emit_state(self, presence: str) -> None:
        s = self.ctl.snapshot()
        self._emit({
            "type": "state", "version": STATE_VERSION,
            "command_id": s.get("command_id", 0), "work_mode": s["mode"],
            "run_state": "RUNNING" if s.get("running", True) else "STOPPED",
            "presence_state": presence, "timestamp_us": int(self.clock() * 1e6),
        })
        self.last_presence = presence

    # -- classification of one target (tune already done by the scheduler) ---
    def _classify_one(self, center_hz: int, raw: np.ndarray) -> tuple[list[dict[str, Any]], float]:
        arm: dict[str, Any] = {}
        try:
            frame = self.recover(np.asarray(raw), self.recover_fn)
        except Exception as exc:
            self.rejected += 1
            return [], 0.0
        if frame is None:
            self.rejected += 1
            return [], 0.0
        arm.update(frame.metadata)
        arm["input_sha256"] = frame.tensor_sha256
        try:
            arm.update(self.infer(frame.tensor))
            arm["finite"] = True
            self.valid += 1
        except Exception as exc:
            arm["pred"] = -1
            arm["finite"] = False
            arm["error"] = type(exc).__name__ + ": " + str(exc)
            self.rejected += 1
        event = self.build_ui_event(self.seq, arm, display_tensor=frame.tensor)
        result = self.build_board_ui_result(event, center_hz=center_hz,
                                            work_mode=self.work_mode())
        if result is not None:
            self._emit(result)
        return self._top3(arm)

    # -- one full frame iteration --------------------------------------------
    def step(self) -> dict[str, Any]:
        """One iteration of the production loop.  Returns a status dict."""
        s = self.ctl.snapshot()
        mode = s["mode"]
        running = bool(s.get("running", True))
        if not running:
            self._emit_state("NO_SIGNAL")
            return {"frame_id": self.seq, "mode": mode, "state": "STOPPED"}

        if mode == "FIXED":
            return self._step_fixed()

        # BAND_SCAN (multi-signal scheduler path)
        self.cycle += 1
        if self.ctl.drain(self.radio):
            # Range change: keep targets, cleanup/migrate deterministically.
            self.scheduler.apply_range(self._lo_points())
            return {"frame_id": self.seq, "mode": mode, "state": "RESTART"}

        now = self.clock()
        if self.scheduler.due_for_rescan(self.cycle):
            if self.psd_detect is not None:
                self.scheduler.sweep_psd(self.psd_detect, self.radio.tune,
                                         self._capture, self.radio.flush, now)
            else:
                self.scheduler.sweep(self._safe_detect, self.radio.tune,
                                     self._capture, self.radio.flush, now,
                                     should_stop=self.stop.is_set)
        # Per-target classification (round-robin, budget from scheduler opts).
        self.scheduler.classify_pass(
            self._classify_one, self.radio.tune, self._capture, self.radio.flush,
            now, should_stop=self.stop.is_set
        )
        # Fair revisit (re-detect tracking targets; updates last_seen).
        self.scheduler.revisit(self._safe_detect, self.radio.tune, self._capture,
                               self.radio.flush, now, should_stop=self.stop.is_set)
        self.scheduler.end_cycle()

        # Target-list snapshot for the five-page UI.
        snapshot = self.scheduler.snapshot()
        self.last_event = {
            "type": "rml24_targets", "version": "rml24-multisignal-v1",
            "timestamp_us": int(self.clock() * 1e6),
            "targets": self._json_safe_targets(snapshot),
        }
        self._emit(self.last_event)
        self._emit_state("SIGNAL_PRESENT" if snapshot else "NO_SIGNAL")

        self._write_records(mode, snapshot)
        self.seq += 1
        return {"frame_id": self.seq - 1, "mode": mode, "state": "SCANNED",
                "targets": len(snapshot)}

    def _step_fixed(self) -> dict[str, Any]:
        s = self.ctl.snapshot()
        self.radio.tune(int(s["fixed_hz"]))
        self.radio.flush()
        raw = self._capture()
        arm: dict[str, Any] = {}
        frame = None
        try:
            frame = self.recover(raw, self.recover_fn)
        except Exception:
            frame = None
        if frame is not None:
            arm.update(frame.metadata)
            arm["input_sha256"] = frame.tensor_sha256
            try:
                arm.update(self.infer(frame.tensor))
                arm["finite"] = True
                self.valid += 1
            except Exception as exc:
                arm["pred"] = -1
                arm["finite"] = False
                arm["error"] = type(exc).__name__ + ": " + str(exc)
                self.rejected += 1
            event = self.build_ui_event(self.seq, arm, display_tensor=frame.tensor)
            result = self.build_board_ui_result(event, center_hz=int(s["fixed_hz"]),
                                                work_mode="FIXED")
            if result is not None:
                self._emit(result)
            self._emit_state("SIGNAL_PRESENT" if arm.get("finite") else "NO_SIGNAL")
        else:
            arm = {"pred": -1, "finite": False, "error": "NO_VALID_PUBLIC_FRAME"}
            self.rejected += 1
            self._emit_state("NO_SIGNAL")
        self._write_records("FIXED", None)
        self.seq += 1
        return {"frame_id": self.seq - 1, "mode": "FIXED",
                "state": "IDENTIFIED" if arm.get("finite") else "NO_SIGNAL"}

    def _write_records(self, mode: str, targets: list[dict[str, Any]] | None) -> None:
        if self.cfg.out_dir is None:
            return
        self.cfg.out_dir.mkdir(parents=True, exist_ok=True)
        row = {"frame_id": self.seq, "mode": mode,
               "targets": targets if targets is not None else [],
               "valid": self.valid, "rejected": self.rejected}
        with (self.cfg.out_dir / "records.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    def run(self, max_frames: int | None = None) -> int:
        """Run until stop/duration; returns number of frames processed."""
        n = 0
        while not self.stop.is_set():
            if max_frames is not None and n >= max_frames:
                break
            if self.cfg.duration_sec and self.clock() - self.started >= self.cfg.duration_sec:
                self.stop.set()
                break
            self.step()
            n += 1
        return n
