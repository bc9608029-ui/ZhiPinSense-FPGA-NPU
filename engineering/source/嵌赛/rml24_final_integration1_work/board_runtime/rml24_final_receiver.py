#!/usr/bin/env python3
"""Formal label-blind board receiver for the frozen two-DC candidate.

Hardware imports are intentionally delayed so host tests can import this file.
The transmitter control protocol carries sequence identity only; no class label,
expected prediction, source payload, or per-sample recovery parameter is read.
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

from receiver_core import recover_frame, summarize_logits  # noqa: E402
from ui_event import build_board_ui_result, build_ui_event  # noqa: E402
import candidate_two_dc  # noqa: E402


class UiSocketClient:
    """Fail-soft JSONL client; UI outages never stop capture or inference."""

    def __init__(self, path: str | None) -> None:
        self.path = path
        self.connection: socket.socket | None = None
        self.sent = 0
        self.failed = 0

    def _connect(self) -> None:
        if not self.path or self.connection is not None:
            return
        candidate = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        candidate.settimeout(0.25)
        try:
            candidate.connect(self.path)
        except OSError:
            candidate.close()
            raise
        self.connection = candidate

    def send(self, event: dict[str, Any]) -> None:
        if not self.path:
            return
        payload = (json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        try:
            self._connect()
            assert self.connection is not None
            self.connection.sendall(payload)
            self.sent += 1
        except OSError as exc:
            self.failed += 1
            self.close()
            print(f"RML24_FINAL_UI_SEND status=RETRY error={type(exc).__name__}", flush=True)

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


def write_json_atomic(path: Path, value: Any) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(temporary, path)


def infer(npu: socket.socket, tensor: np.ndarray) -> dict[str, Any]:
    rows = []
    for window in tensor:
        npu.sendall(window.astype("<f4", copy=False).tobytes(order="C"))
        rows.append(np.frombuffer(exact(npu, 24 * 4), dtype="<f4").copy())
    return summarize_logits(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--npu-socket", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--legacy-root", required=True, help="Directory containing pluto_link_probe.py and pilot_recovery.py")
    parser.add_argument("--control-host", default="192.168.126.10")
    parser.add_argument("--control-port", type=int, default=39012)
    parser.add_argument("--mode", choices=("candidate", "paired"), default="candidate")
    parser.add_argument("--ui-socket", default="/run/sdr_amr_ui_rml24_final.sock")
    parser.add_argument("--save-raw", action="store_true")
    parser.add_argument("--save-tensor", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)

    legacy_root = Path(args.legacy_root).resolve()
    sys.path.insert(0, str(legacy_root))
    link = importlib.import_module("pluto_link_probe")
    baseline = importlib.import_module("pilot_recovery") if args.mode == "paired" else None

    uris = link.scan_usb()
    if len(uris) != 1:
        raise RuntimeError(f"expected exactly one RX Pluto, got {uris!r}")

    radio = link.Radio(uris[0])
    npu: socket.socket | None = None
    control: socket.socket | None = None
    records: list[dict[str, Any]] = []
    restore_errors: list[str] = []
    ui_client = UiSocketClient(args.ui_socket or None)
    try:
        radio.config_rx()
        npu = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        npu.settimeout(20)
        npu.connect(args.npu_socket)
        control = socket.create_connection((args.control_host, args.control_port), timeout=30)
        stream = control.makefile("rwb", buffering=0)

        while True:
            stream.write(b"NEXT\n")
            message = json.loads(stream.readline())
            if message.get("done"):
                break
            if set(message) - {"seq"}:
                raise RuntimeError(f"control message contains forbidden fields: {sorted(set(message) - {'seq'})}")
            seq = int(message["seq"])
            started = time.monotonic()
            raw = radio.receive(65536)
            if args.save_raw:
                np.save(out / f"{seq:04d}.raw.npy", raw)
            stream.write(b"CAPTURED\n")
            stopped = json.loads(stream.readline())
            if not stopped.get("stopped"):
                raise RuntimeError("transmitter did not acknowledge stop")

            row: dict[str, Any] = {"seq": seq, "arms": {}}
            candidate_tensor: np.ndarray | None = None
            arms = [("candidate", candidate_two_dc)]
            if baseline is not None:
                arms.insert(0, ("baseline", baseline))
            for name, module in arms:
                arm: dict[str, Any] = {}
                try:
                    frame = recover_frame(raw, module.recover)
                    if name == "candidate":
                        candidate_tensor = frame.tensor
                    arm.update(frame.metadata)
                    arm["input_sha256"] = frame.tensor_sha256
                    if args.save_tensor:
                        (out / f"{seq:04d}.{name}.inputs.bin").write_bytes(frame.tensor_bytes)
                    arm.update(infer(npu, frame.tensor))
                    arm["finite"] = True
                except Exception as exc:  # preserve the full denominator
                    arm.update(error=f"{type(exc).__name__}: {exc}", finite=False, pred=-1)
                row["arms"][name] = arm
            row["elapsed_ms"] = (time.monotonic() - started) * 1000.0
            records.append(row)
            ui_event = build_ui_event(seq, row["arms"]["candidate"], display_tensor=candidate_tensor)
            with (out / "ui_events.jsonl").open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(json.dumps(ui_event, ensure_ascii=False, separators=(",", ":")) + "\n")
            board_ui_result = build_board_ui_result(ui_event)
            if board_ui_result is not None:
                ui_client.send(board_ui_result)
            write_json_atomic(
                out / "results.json",
                {
                    "kind": "RML24_FINAL_LABEL_BLIND_RX_V1",
                    "receiver_has_labels": False,
                    "mode": args.mode,
                    "records": records,
                },
            )
            print(json.dumps({"seq": seq, "candidate": row["arms"]["candidate"].get("pred", -1)}), flush=True)
    finally:
        if control is not None:
            control.close()
        if npu is not None:
            npu.close()
        ui_client.close()
        try:
            close_result = radio.close()
            restore_errors = [] if close_result is None else list(close_result)
        finally:
            write_json_atomic(out / "restore.json", restore_errors)

    print(
        f"RML24_FINAL_RX_COMPLETE frames={len(records)} restore_errors={len(restore_errors)} "
        f"ui_sent={ui_client.sent} ui_failed={ui_client.failed}",
        flush=True,
    )
    return 0 if not restore_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())

