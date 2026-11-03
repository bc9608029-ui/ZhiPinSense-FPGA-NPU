"""Injectable receiver entry with A-line fidelity restored (AC integration).

This is the C-line ``receiver_entry.ReceiverEntry`` with the A-line fidelity
features re-added, so the multi-signal candidate mode is *not* a behaviourally
degraded replacement of the frozen single-target loop.  The original
``standalone_receiver.py`` (SHA ``4d35cf5e``) is KEPT as the default/fallback
entry; this module backs the NEW candidate entry
``standalone_receiver_multisignal.py`` only.

Fidelity reconciliation vs the A-line ``standalone_receiver.py`` loop:

* **Feature measurement** -- RMS/peak/energy + ``feature_latency_us`` +
  ``backend`` are measured AFTER a successful inference (exact A-line math:
  ``z=(I+1jQ).mean(axis=0)`` over the 8 payload windows) and pushed to the
  controller via ``ctl.update(frame_id=..., rms_iq=..., peak_iq=...,
  energy_iq2=..., feature_latency_us=..., backend='software')``.
* **state() event** -- carries ``model_sha`` and is throttled to 0.5 s
  (``force`` bypasses the throttle), matching the A-line ``state()`` helper;
  ``presence`` is written to the controller on every call (even throttled).
* **records.jsonl** -- FIXED mode writes the FULL A-line row schema
  (``frame_id/mode/capture_time_ns/board_monotonic/center_hz/actual_lo_hz/
  candidate/scan_steps/elapsed_ms``); BAND_SCAN mode writes the same base
  fields plus a ``targets`` snapshot (the multi-signal core).
* **--save-captures** -- FIXED mode writes ``%06d.raw.npy`` + ``%06d.inputs.bin``
  exactly like the A-line; BAND_SCAN mode writes ``%06d_c<center_hz>.raw.npy``
  + ``%06d_c<center_hz>.inputs.bin`` (one capture per classified target).
* **status.json** -- written every frame (valid/rejected/records/tuning), the
  A-line schema.  final.json is written by the entry-point ``main`` (it owns
  restore/ui counters).
* **NPU inference failure** -- FIXED mode keeps the A-line contract "failure of
  real NPU inference is fatal, not disguised as no signal" (the exception
  propagates).  BAND_SCAN mode marks the target unclassified and continues
  (documented, tested difference; the global state still reports SIGNAL_PRESENT
  while targets exist, so an infer failure is never disguised as NO_SIGNAL).

Every board dependency is constructor-injected (radio/infer/transport/clock/
detector/recover/controller/psd_detect) so the offline tests drive this exact
loop; the board entry wires the real radio/NPU/UI/control in ``main``.
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
# Frozen RAW24 model identity (same value as ui_event.MODEL_SHA / A-line state()).
MODEL_SHA = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"
STATE_THROTTLE_SEC = 0.5


def _atomic_write_json(path: Path, obj: Any) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj), encoding="utf-8")
    tmp.replace(path)


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
    """Minimal always-running controller when none is injected (offline tests)."""

    def __init__(self, cfg: EntryConfig) -> None:
        self._s: dict[str, Any] = {
            "mode": cfg.initial_mode, "running": True,
            "start_hz": cfg.scan_start_hz, "stop_hz": cfg.scan_stop_hz,
            "step_hz": cfg.scan_step_hz, "fixed_hz": cfg.fixed_center_hz,
            "command_id": 0,
        }

    def snapshot(self) -> dict[str, Any]:
        return dict(self._s)

    def update(self, **values: Any) -> None:
        self._s.update(values)

    def drain(self, lo: Any) -> bool:
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
        self._last_state_ts = 0.0
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
        """JSON-safe target records: unmeasured power (internal NaN) -> null."""
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

    def _measure_and_update(self, tensor: np.ndarray, seq: int) -> None:
        """A-line feature measurement (exact math), pushed to the controller."""
        measure_start = time.monotonic_ns()
        z = (tensor[:, 0, :] + 1j * tensor[:, 1, :]).mean(axis=0, dtype=np.complex128)
        energy = float(np.sum(np.abs(z) ** 2))
        self.ctl.update(
            frame_id=seq,
            rms_iq=float(np.sqrt(energy / 1024)),
            peak_iq=float(np.max(np.abs(z))),
            energy_iq2=energy,
            feature_latency_us=(time.monotonic_ns() - measure_start) / 1000,
            backend="software",
        )

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

    def _emit_state(self, presence: str, force: bool = False) -> None:
        """A-line state() helper: write presence, throttle 0.5 s, carry model_sha."""
        try:
            self.ctl.update(presence=presence)
        except Exception:
            pass
        now = self.clock()
        if not force and now - self._last_state_ts < STATE_THROTTLE_SEC:
            return
        s = self.ctl.snapshot()
        self._emit({
            "type": "state", "version": STATE_VERSION,
            "command_id": s.get("command_id", 0), "work_mode": s["mode"],
            "run_state": "RUNNING" if s.get("running", True) else "STOPPED",
            "presence_state": presence,
            "timestamp_us": time.time_ns() // 1000,
            "model_sha": MODEL_SHA,
        })
        self._last_state_ts = now
        self.last_presence = presence

    # -- save-captures (A-line schema for FIXED, per-target for BAND_SCAN) ---
    def _save_capture_fixed(self, raw: np.ndarray | None, frame: Any, seq: int) -> None:
        if not self.cfg.save_captures or self.cfg.out_dir is None:
            return
        if raw is not None:
            np.save(self.cfg.out_dir / ("%06d.raw.npy" % seq), raw)
            if frame is not None:
                (self.cfg.out_dir / ("%06d.inputs.bin" % seq)).write_bytes(frame.tensor_bytes)

    def _save_capture_scan(self, raw: np.ndarray, frame: Any, seq: int, center_hz: int) -> None:
        if not self.cfg.save_captures or self.cfg.out_dir is None:
            return
        np.save(self.cfg.out_dir / ("%06d_c%d.raw.npy" % (seq, center_hz)), raw)
        if frame is not None:
            (self.cfg.out_dir / ("%06d_c%d.inputs.bin" % (seq, center_hz))).write_bytes(frame.tensor_bytes)

    # -- classification of one target (tune already done by the scheduler) ---
    def _classify_one(self, center_hz: int, raw: np.ndarray) -> tuple[list[dict[str, Any]], float]:
        arm: dict[str, Any] = {}
        frame = None
        try:
            frame = self.recover(np.asarray(raw), self.recover_fn)
        except Exception as exc:
            arm = {"pred": -1, "finite": False,
                   "error": type(exc).__name__ + ": " + str(exc)}
        if frame is None:
            arm.setdefault("pred", -1)
            arm.setdefault("finite", False)
            arm.setdefault("error", "NO_VALID_PUBLIC_FRAME")
            self.rejected += 1
            return [], 0.0
        arm.update(frame.metadata)
        arm["input_sha256"] = frame.tensor_sha256
        try:
            arm.update(self.infer(frame.tensor))
            arm["finite"] = True
            self.valid += 1
            self._measure_and_update(frame.tensor, self.seq)
        except Exception as exc:
            # BAND_SCAN: mark unclassified and continue (never disguised as no signal).
            arm["pred"] = -1
            arm["finite"] = False
            arm["error"] = type(exc).__name__ + ": " + str(exc)
            self.rejected += 1
        event = self.build_ui_event(self.seq, arm, display_tensor=frame.tensor)
        result = self.build_board_ui_result(event, center_hz=center_hz,
                                            work_mode=self.work_mode())
        if result is not None:
            self._emit(result)
        self._save_capture_scan(raw, frame, self.seq, center_hz)
        return self._top3(arm)

    # -- one full frame iteration --------------------------------------------
    def step(self) -> dict[str, Any]:
        """One iteration of the production loop.  Returns a status dict."""
        s = self.ctl.snapshot()
        mode = s["mode"]
        running = bool(s.get("running", True))
        if not running:
            self._emit_state("NO_SIGNAL", force=True)
            return {"frame_id": self.seq, "mode": mode, "state": "STOPPED"}

        if mode == "FIXED":
            return self._step_fixed()

        # BAND_SCAN (multi-signal scheduler path)
        self.cycle += 1
        if self.ctl.drain(self.radio):
            # Range change: keep targets, cleanup/migrate deterministically.
            self.scheduler.apply_range(self._lo_points())
            return {"frame_id": self.seq, "mode": mode, "state": "RESTART"}

        begin = self.clock()
        now = self.clock()
        rescan = self.scheduler.due_for_rescan(self.cycle)
        if rescan:
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
            "timestamp_us": time.time_ns() // 1000,
            "targets": self._json_safe_targets(snapshot),
        }
        self._emit(self.last_event)
        self._emit_state("SIGNAL_PRESENT" if snapshot else "NO_SIGNAL")

        scan_steps = [dict(rescan=True, dwell_count=len(self._lo_points()))] if rescan else []
        row = dict(
            frame_id=self.seq, mode="BAND_SCAN",
            capture_time_ns=time.time_ns(), board_monotonic=time.monotonic(),
            center_hz=None, actual_lo_hz=None, candidate={},
            scan_steps=scan_steps, elapsed_ms=(self.clock() - begin) * 1000,
            targets=self._json_safe_targets(snapshot),
        )
        self._write_record(row)
        self._write_status()
        self.seq += 1
        return {"frame_id": self.seq - 1, "mode": mode, "state": "SCANNED",
                "targets": len(snapshot)}

    def _step_fixed(self) -> dict[str, Any]:
        """FIXED mode: the A-line single-result behaviour, byte-faithful.

        Recover failure -> no-signal; NPU infer failure -> FATAL (propagates),
        exactly the A-line contract.  Feature measurement + state() model_sha +
        full records + save-captures are restored here.
        """
        s = self.ctl.snapshot()
        begin = self.clock()
        if getattr(self.radio, "current_hz", None) != s["fixed_hz"]:
            actual = self.radio.tune(int(s["fixed_hz"]))
            self.radio.flush()
            self.ctl.update(actual_lo_hz=actual, fixed_readback_hz=actual)
        self._emit_state("ACQUIRING")
        raw = self._capture()
        capture_ns = time.time_ns()
        center = int(s["fixed_hz"])
        arm: dict[str, Any] = {}
        tensor = None
        frame = None
        try:
            frame = self.recover(raw, self.recover_fn)
        except Exception as exc:
            arm = {"pred": -1, "finite": False,
                   "error": type(exc).__name__ + ": " + str(exc)}
        if frame is not None:
            tensor = frame.tensor
            arm.update(frame.metadata, input_sha256=frame.tensor_sha256)
            # Failure of real NPU inference is fatal, not disguised as no signal.
            arm.update(self.infer(tensor))  # NOT caught: fatal on failure
            arm["finite"] = True
            self.valid += 1
            self._measure_and_update(tensor, self.seq)
            event = self.build_ui_event(self.seq, arm, display_tensor=tensor)
            result = self.build_board_ui_result(event, center_hz=center, work_mode="FIXED")
            if result is not None:
                self._emit(result)
            self._emit_state("SIGNAL_PRESENT", force=True)
        else:
            arm.setdefault("pred", -1)
            arm.setdefault("finite", False)
            arm.setdefault("error", "NO_VALID_PUBLIC_FRAME")
            self.rejected += 1
            self._emit_state("NO_SIGNAL", force=True)
        row = dict(
            frame_id=self.seq, mode="FIXED", capture_time_ns=capture_ns,
            board_monotonic=time.monotonic(), center_hz=center,
            actual_lo_hz=getattr(self.radio, "current_hz", center),
            candidate=arm, scan_steps=[], elapsed_ms=(self.clock() - begin) * 1000,
        )
        self._save_capture_fixed(raw if frame is not None else None, frame, self.seq)
        self._write_record(row)
        self._write_status()
        self.seq += 1
        return {"frame_id": self.seq - 1, "mode": "FIXED",
                "state": "IDENTIFIED" if arm.get("finite") else "NO_SIGNAL"}

    # -- records / status ----------------------------------------------------
    def _write_record(self, row: dict[str, Any]) -> None:
        if self.cfg.out_dir is None:
            return
        self.cfg.out_dir.mkdir(parents=True, exist_ok=True)
        with (self.cfg.out_dir / "records.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")

    def _write_status(self) -> None:
        if self.cfg.out_dir is None:
            return
        self.cfg.out_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_json(
            self.cfg.out_dir / "status.json",
            dict(valid=self.valid, rejected=self.rejected, records=self.seq + 1,
                 no_tcp=True, no_tx_handshake=True, tuning=self.ctl.snapshot()),
        )

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
