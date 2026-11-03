#!/usr/bin/env python3
"""Final dual-Pluto transmitter with a public, configurable RF centre.

The default remains byte/parameter compatible with the verified Stage-7 fixed
test.  ``--center-hz`` changes only the public RF tuning parameter; payloads,
frame structure, scaling, labels and the receiver control protocol are unchanged.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import socket
import sys
import time
from pathlib import Path
from typing import Any

import numpy as np


SCALE = 68.46059377833956
SAMPLE_RATE = 2_560_000
BANDWIDTH = 18_000_000
CENTER_HZ = 2_400_000_000
TX_ATTEN_DB = -40.0


def load_manifest(path: Path) -> list[dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    records = document.get("records", [])
    if not records:
        raise ValueError("empty transmit manifest")
    required = {"seq", "file", "source_sha256"}
    cleaned = []
    seen = set()
    for row in records:
        if not required <= set(row):
            raise ValueError("manifest row lacks seq/file/source_sha256")
        seq = int(row["seq"])
        if seq in seen:
            raise ValueError(f"duplicate seq {seq}")
        seen.add(seq)
        digest = str(row["source_sha256"])
        if len(digest) != 64:
            raise ValueError(f"bad source SHA for seq {seq}")
        cleaned.append({"seq": seq, "file": str(row["file"]), "source_sha256": digest})
    return cleaned


def build_frame(payload_bytes: bytes, train: np.ndarray, tail: np.ndarray) -> np.ndarray:
    values = np.frombuffer(payload_bytes, dtype="<f4")
    if values.size != 2048:
        raise ValueError(f"payload must contain 2048 float32 values, got {values.size}")
    iq = values.reshape(2, 1024)
    source = iq[0] + 1j * iq[1]
    frame = np.concatenate(
        [
            np.zeros(2048, dtype=np.complex64),
            np.asarray(train, dtype=np.complex64),
            np.tile(source, 8),
            np.asarray(tail, dtype=np.complex64),
            np.zeros(2048, dtype=np.complex64),
        ]
    ).astype(np.complex64)
    scaled = frame * SCALE
    component_peak = float(max(np.abs(scaled.real).max(), np.abs(scaled.imag).max()))
    if not np.isfinite(scaled).all() or component_peak > 2047.0:
        raise ValueError(f"scaled TX frame invalid or clips: component_peak={component_peak}")
    return scaled


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--legacy-root", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--listen-host", default="192.168.126.10")
    parser.add_argument("--port", type=int, default=39012)
    parser.add_argument("--tx-uri")
    parser.add_argument("--settle-ms", type=float, default=80.0)
    parser.add_argument("--center-hz", type=int, default=CENTER_HZ)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    records = load_manifest(args.manifest)
    sys.path.insert(0, str(args.legacy_root.resolve()))
    link = importlib.import_module("pluto_link_probe")
    protocol = importlib.import_module("pilot_recovery")
    uris = [args.tx_uri] if args.tx_uri else link.scan_usb()
    if len(uris) != 1:
        raise RuntimeError(f"expected exactly one TX Pluto, got {uris!r}")

    radio = link.Radio(uris[0])
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((args.listen_host, args.port))
    listener.listen(1)
    listener.settimeout(180)
    buffer = None
    tx_rows = []
    restore_errors: list[str] = []
    try:
        radio.set(radio.tx, "hardwaregain", TX_ATTEN_DB)
        radio.set(radio.tx, "sampling_frequency", SAMPLE_RATE)
        radio.set(radio.tx, "rf_bandwidth", BANDWIDTH)
        if args.center_hz <= 0:
            raise ValueError("center-hz must be positive")
        radio.set(radio.tlo, "frequency", args.center_hz)
        print(
            f"RML24_SCAN_TX_LISTENING frames={len(records)} uri={uris[0]} "
            f"center_hz={args.center_hz}",
            flush=True,
        )
        connection, peer = listener.accept()
        connection.settimeout(180)
        print(f"RML24_FINAL_TX_CONNECTED peer={peer[0]}:{peer[1]}", flush=True)
        with connection, connection.makefile("rwb", buffering=0) as stream:
            session_finished = False
            for item in records:
                if stream.readline() != b"NEXT\n":
                    raise RuntimeError("receiver protocol mismatch before transmit")
                if (args.out / "finish_requested").exists():
                    stream.write(b'{"done":true}\n')
                    session_finished = True
                    break
                source_path = args.dataset / item["file"]
                payload = source_path.read_bytes()
                actual_sha = hashlib.sha256(payload).hexdigest()
                if actual_sha != item["source_sha256"]:
                    raise RuntimeError(f"payload SHA mismatch for seq {item['seq']}")
                frame = build_frame(payload, protocol.train, protocol.tail)
                buffer = radio.send(frame)
                time.sleep(args.settle_ms / 1000.0)
                # Only sequence identity crosses the control channel. No label,
                # truth, source IQ, or per-sample recovery parameter is sent.
                stream.write((json.dumps({"seq": item["seq"]}) + "\n").encode("utf-8"))
                if stream.readline() != b"CAPTURED\n":
                    raise RuntimeError("receiver protocol mismatch after capture")
                radio.stop(buffer)
                buffer = None
                stream.write(b'{"stopped":true}\n')
                tx_rows.append({"seq": item["seq"], "source_sha256": actual_sha})
                print(f"RML24_FINAL_TX_FRAME seq={item['seq']}", flush=True)
            if not session_finished:
                if stream.readline() != b"NEXT\n":
                    raise RuntimeError("receiver did not request completion")
                stream.write(b'{"done":true}\n')
    finally:
        if buffer is not None:
            radio.stop(buffer)
        close_result = radio.close()
        restore_errors = [] if close_result is None else list(close_result)
        listener.close()
        (args.out / "tx_results.json").write_text(
            json.dumps({"kind": "UI_INTERACTIVE_DIAGNOSTIC_NOT_ACCURACY", "records": tx_rows, "restore_errors": restore_errors}, indent=2) + "\n",
            encoding="utf-8",
        )
    print(f"RML24_FINAL_TX_COMPLETE frames={len(tx_rows)} restore_errors={len(restore_errors)}", flush=True)
    return 0 if not restore_errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
