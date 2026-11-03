#!/usr/bin/env python3
"""Final label-blind RML24 receiver with FIXED and BAND_SCAN modes.

FIXED keeps the verified Stage-7 recovery path.  BAND_SCAN changes only RX LO
selection and a public-training coarse CFO correction, then calls the same
``candidate_two_dc.recover`` and frozen NPU inference path.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "recovery"))

from mode_control_server import ModeControlServer, ModeState  # noqa: E402
from radio_tuning import RxLoController  # noqa: E402
from receiver_core import recover_frame, summarize_logits  # noqa: E402
from scan_runtime import (  # noqa: E402
    ScanConfig,
    ScanHit,
    detect_public_training,
    remove_coarse_cfo,
    scan_and_select,
)
from ui_event import build_board_ui_result, build_ui_event  # noqa: E402
import candidate_two_dc  # noqa: E402


class UiSocketClient:
    def __init__(self, path: str | None) -> None:
        self.path = path
        self.connection: socket.socket | None = None
        self.sent = 0
        self.failed = 0

    def send(self, event: dict[str, Any]) -> None:
        if not self.path:
            return
        payload = (json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            if self.connection is None:
                self.connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                self.connection.settimeout(0.25)
                self.connection.connect(self.path)
            self.connection.sendall(payload)
            self.sent += 1
        except OSError as exc:
            self.failed += 1
            self.close()
            print(f"RML24_DUALMODE_UI_SEND status=RETRY error={type(exc).__name__}", flush=True)

    def close(self) -> None:
        if self.connection is not None:
            self.connection.close()
            self.connection = None


def exact(sock: socket.socket, count: int) -> bytes:
    chunks: list[bytes] = []
    while count:
        block = sock.recv(count)
        if not block:
            raise RuntimeError("NPU stream closed")
        chunks.append(block)
        count -= len(block)
    return b"".join(chunks)


def infer(npu: socket.socket, tensor: np.ndarray) -> dict[str, Any]:
    rows = []
    for window in tensor:
        npu.sendall(window.astype("<f4", copy=False).tobytes(order="C"))
        rows.append(np.frombuffer(exact(npu, 24 * 4), dtype="<f4").copy())
    return summarize_logits(rows)


def write_json_atomic(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--npu-socket", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--legacy-root", required=True)
    parser.add_argument("--control-host", default="192.168.126.10")
    parser.add_argument("--control-port", type=int, default=39012)
    parser.add_argument("--ui-socket", default="/run/sdr_amr_ui_rml24_final.sock")
    parser.add_argument("--ui-control-socket", default="/run/sdr_amr_control_rml24_final.sock")
    parser.add_argument("--initial-mode", choices=("FIXED", "BAND_SCAN"), default="FIXED")
    parser.add_argument("--fixed-center-hz", type=int, default=2_400_000_000)
    parser.add_argument("--scan-start-hz", type=int, default=2_395_000_000)
    parser.add_argument("--scan-stop-hz", type=int, default=2_405_000_000)
    parser.add_argument("--scan-step-hz", type=int, default=1_000_000)
    parser.add_argument("--scan-min-public-score", type=float, default=0.10)
    parser.add_argument("--lo-readback-tolerance-hz", type=int, default=5_000)
    parser.add_argument("--lo-flush-captures", type=int, default=2)
    parser.add_argument("--save-raw", action="store_true")
    parser.add_argument("--save-tensor", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    config = ScanConfig(
        start_hz=args.scan_start_hz,
        stop_hz=args.scan_stop_hz,
        step_hz=args.scan_step_hz,
        min_public_score=args.scan_min_public_score,
        readback_tolerance_hz=args.lo_readback_tolerance_hz,
    )
    config.validate()

    legacy_root = Path(args.legacy_root).resolve()
    sys.path.insert(0, str(legacy_root))
    link = importlib.import_module("pluto_link_probe")
    protocol = importlib.import_module("pilot_recovery")
    uris = link.scan_usb()
    if len(uris) != 1:
        raise RuntimeError(f"expected exactly one RX Pluto, got {uris!r}")

    radio = link.Radio(uris[0])
    npu: socket.socket | None = None
    tx_control: socket.socket | None = None
    lo: RxLoController | None = None
    mode_state = ModeState()
    if args.initial_mode != "FIXED":
        mode_state.apply(f"SET_MODE {args.initial_mode}")
    mode_server = ModeControlServer(args.ui_control_socket, mode_state)
    ui_client = UiSocketClient(args.ui_socket or None)
    records: list[dict[str, Any]] = []
    restore_errors: list[str] = []
    locked_lo_hz: int | None = None
    try:
        radio.config_rx()
        lo = RxLoController(radio, args.lo_readback_tolerance_hz, args.lo_flush_captures)
        lo.tune(args.fixed_center_hz)
        mode_server.start()
        npu = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        npu.settimeout(20)
        npu.connect(args.npu_socket)
        tx_control = socket.create_connection((args.control_host, args.control_port), timeout=30)
        stream = tx_control.makefile("rwb", buffering=0)
        print(
            f"RML24_DUALMODE_READY fixed_center_hz={args.fixed_center_hz} "
            f"scan={args.scan_start_hz}:{args.scan_stop_hz}:{args.scan_step_hz}",
            flush=True,
        )

        while True:
            state = mode_state.snapshot()
            if not state.running:
                time.sleep(0.05)
                continue
            stream.write(b"NEXT\n")
            message = json.loads(stream.readline())
            if message.get("done"):
                break
            if set(message) - {"seq"}:
                raise RuntimeError(f"control message contains forbidden fields: {sorted(set(message) - {'seq'})}")
            seq = int(message["seq"])
            started = time.monotonic()
            row: dict[str, Any] = {"seq": seq, "mode": state.mode}
            display_center_hz = args.fixed_center_hz
            raw_for_recovery: np.ndarray | None = None

            if state.mode == "FIXED":
                locked_lo_hz = None
                if lo.current_hz != args.fixed_center_hz:
                    lo.tune(args.fixed_center_hz)
                    lo.flush()
                raw_for_recovery = np.asarray(radio.receive(65536))
                row["scan_steps"] = []
            else:
                hit = None
                scan_steps: list[dict[str, Any]] = []
                # Once a public frame is found, stay locked and use one capture
                # per following payload. A failed public check drops the lock and
                # immediately performs a bounded rescan while TX remains cyclic.
                if locked_lo_hz is not None:
                    if lo.current_hz != locked_lo_hz:
                        lo.tune(locked_lo_hz)
                        lo.flush()
                    locked_raw = np.asarray(radio.receive(65536))
                    locked_detection = detect_public_training(locked_raw, protocol.train)
                    locked_ok = (locked_detection.score >= config.min_public_score and abs(locked_detection.coarse_cfo_hz) <= 1000.0)
                    scan_steps.append(
                        {
                            "requested_lo_hz": locked_lo_hz,
                            "actual_lo_hz": lo.current_hz,
                            "public_start": locked_detection.start,
                            "coarse_cfo_hz": locked_detection.coarse_cfo_hz,
                            "public_score": locked_detection.score,
                            "accepted": locked_ok,
                            "locked_check": True,
                        }
                    )
                    if locked_ok:
                        hit = ScanHit(
                            lo_hz=lo.current_hz,
                            signal_hz=float(lo.current_hz + locked_detection.coarse_cfo_hz),
                            detection=locked_detection,
                            raw_iq=locked_raw,
                        )
                    else:
                        locked_lo_hz = None
                if hit is None:
                    hit, sweep_steps = scan_and_select(
                        config,
                        protocol.train,
                        lo.tune,
                        lambda: np.asarray(radio.receive(65536)),
                        lo.flush,
                    )
                    scan_steps.extend(sweep_steps)
                row["scan_steps"] = scan_steps
                if hit is not None:
                    try:
                        # Candidate: centre the physical LO before frozen recovery.
                        # Public-reference CFO is a discovery estimate, not an IQ
                        # preprocessing step that removes the frozen two-DC basis.
                        initial_lo = hit.lo_hz
                        requested_center = int(round(hit.signal_hz))
                        if abs(hit.detection.coarse_cfo_hz) > 1000.0:
                            lo.tune(requested_center)
                            lo.flush()
                            centered_raw = np.asarray(radio.receive(65536))
                            centered_detection = detect_public_training(centered_raw, protocol.train)
                            if centered_detection.score < config.min_public_score or abs(centered_detection.coarse_cfo_hz) > 1000.0:
                                raise RuntimeError("public-centre verification failed")
                            hit = ScanHit(lo_hz=lo.current_hz,
                                signal_hz=float(lo.current_hz + centered_detection.coarse_cfo_hz),
                                detection=centered_detection, raw_iq=centered_raw)
                            row["public_centering"] = {
                                "initial_grid_lo_hz": initial_lo,
                                "requested_lo_hz": requested_center,
                                "actual_lo_hz": lo.current_hz,
                                "residual_cfo_hz": centered_detection.coarse_cfo_hz,
                                "public_score": centered_detection.score}
                        locked_lo_hz = hit.lo_hz
                        display_center_hz = int(round(hit.signal_hz))
                        raw_for_recovery = hit.raw_iq
                        row["scan_hit"] = {
                            "lo_hz": hit.lo_hz,
                            "signal_hz": hit.signal_hz,
                            "coarse_cfo_hz": hit.detection.coarse_cfo_hz,
                            "public_score": hit.detection.score,
                        }
                    except Exception as exc:
                        locked_lo_hz = None
                        raw_for_recovery = None
                        row["error"] = "PUBLIC_CENTERING_FAILED:" + type(exc).__name__ + ":" + str(exc)
                else:
                    row["error"] = "NO_PUBLIC_FRAME_IN_SCAN_RANGE"

            # TX remains cyclic throughout a complete scan and stops only here.
            if args.save_raw and raw_for_recovery is not None:
                np.save(out / f"{seq:04d}.{state.mode.lower()}.raw.npy", raw_for_recovery)
            stream.write(b"CAPTURED\n")
            stopped = json.loads(stream.readline())
            if not stopped.get("stopped"):
                raise RuntimeError("transmitter did not acknowledge stop")

            candidate_tensor: np.ndarray | None = None
            arm: dict[str, Any] = {}
            if raw_for_recovery is not None:
                try:
                    frame = recover_frame(raw_for_recovery, candidate_two_dc.recover)
                    candidate_tensor = frame.tensor
                    arm.update(frame.metadata)
                    arm["input_sha256"] = frame.tensor_sha256
                    if args.save_tensor:
                        (out / f"{seq:04d}.candidate.inputs.bin").write_bytes(frame.tensor_bytes)
                    arm.update(infer(npu, frame.tensor))
                    arm["finite"] = True
                except Exception as exc:
                    arm.update(error=f"{type(exc).__name__}: {exc}", finite=False, pred=-1)
                    if state.mode == "BAND_SCAN":
                        locked_lo_hz = None
            else:
                arm.update(error=row["error"], finite=False, pred=-1)
            row["candidate"] = arm
            row["elapsed_ms"] = (time.monotonic() - started) * 1000.0
            records.append(row)

            ui_event = build_ui_event(seq, arm, display_tensor=candidate_tensor)
            with (out / "ui_events.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(ui_event, ensure_ascii=False, separators=(",", ":")) + "\n")
            board_ui_result = build_board_ui_result(
                ui_event,
                center_hz=display_center_hz,
                work_mode="BAND SCAN" if state.mode == "BAND_SCAN" else "FIXED",
                run_state="RUNNING",
            )
            if board_ui_result is not None:
                ui_client.send(board_ui_result)
            write_json_atomic(
                out / "results.json",
                {
                    "kind": "RML24_FINAL_DUALMODE_LABEL_BLIND_RX_V1",
                    "receiver_has_labels": False,
                    "fixed_stage7_recovery_unchanged": True,
                    "records": records,
                },
            )
            print(
                json.dumps(
                    {"seq": seq, "mode": state.mode, "pred": arm.get("pred", -1), "center_hz": display_center_hz},
                    separators=(",", ":"),
                ),
                flush=True,
            )
    finally:
        mode_server.close()
        if tx_control is not None:
            tx_control.close()
        if npu is not None:
            npu.close()
        ui_client.close()
        if lo is not None:
            try:
                lo.restore()
            except Exception as exc:
                restore_errors.append(f"lo_restore:{type(exc).__name__}:{exc}")
        try:
            close_result = radio.close()
            if close_result is not None:
                restore_errors.extend(str(item) for item in close_result)
        finally:
            write_json_atomic(out / "restore.json", restore_errors)

    print(
        f"RML24_DUALMODE_COMPLETE frames={len(records)} restore_errors={len(restore_errors)} "
        f"ui_sent={ui_client.sent} ui_failed={ui_client.failed}",
        flush=True,
    )
    return 0 if not restore_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

