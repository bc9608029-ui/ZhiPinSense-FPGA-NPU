"""Transmit generated clean v2 IQ in the frozen public-pilot frame.

The RX peer receives sequence numbers only. Labels, clean IQ, hashes and scale
stay in the private PC output directory and are used only for offline scoring.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import socket
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from clean_v2_common import FIXED_SCALE, build_frame, load_clean_samples, load_public_pilots, verify_receiver


def load_pluto_module(rescue_root: Path):
    path = rescue_root / "pluto_link_probe.py"
    spec = importlib.util.spec_from_file_location("clean_v2_frozen_pluto", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def prepare(args):
    verify_receiver(args.rescue_root)
    train, tail = load_public_pilots(args.rescue_root)
    samples = load_clean_samples(args.asset_root)
    order = np.random.default_rng(args.seed).permutation(len(samples)).tolist()
    expected = []
    frames = []
    for seq, index in enumerate(order):
        sample = samples[index]
        frame, scale = build_frame(sample, train, tail)
        if abs(scale - FIXED_SCALE) > 1e-12:
            raise RuntimeError(f"fixed-scale contract violated at source {sample.source_index}: {scale}")
        expected.append({
            "seq": seq,
            "source_index": sample.source_index,
            "class_index": sample.class_index,
            "class_name": sample.class_name,
            "generator_seed": sample.seed,
            "clean_tensor_sha256": sample.source_sha256,
            "digital_pred": sample.digital_pred,
            "digital_correct": sample.digital_correct,
            "tx_scale": scale,
            "source_kind": "generated_clean_v2",
        })
        frames.append(frame)
    return expected, frames


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asset-root", type=Path, default=Path(r"F:\嵌赛\fix10class24_waveform_correct_v2_work"))
    ap.add_argument("--rescue-root", type=Path, default=Path(r"F:\AMR_Rescue_20261025"))
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--bind", default="192.168.126.50")
    ap.add_argument("--port", type=int, default=39012)
    ap.add_argument("--seed", type=int, default=20261026)
    ap.add_argument("--tx-uri", default="")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    expected, frames = prepare(args)
    (args.out / "expected_private.json").write_text(
        json.dumps(expected, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.dry_run:
        print(f"CLEAN_V2_TX_DRY_RUN result=PASS frames={len(frames)} out={args.out}")
        return 0

    pluto = load_pluto_module(args.rescue_root)
    uris = pluto.scan_usb()
    uri = args.tx_uri or (uris[0] if len(uris) == 1 else "")
    if not uri or uri not in uris:
        raise RuntimeError(f"need exactly one selected TX Pluto; discovered={uris}, requested={args.tx_uri!r}")
    radio = pluto.Radio(uri)
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((args.bind, args.port))
    listener.listen(1)
    listener.settimeout(180)
    current = None
    try:
        radio.set(radio.tx, "hardwaregain", -40)
        radio.set(radio.tx, "sampling_frequency", 2560000)
        radio.set(radio.tx, "rf_bandwidth", 18000000)
        radio.set(radio.tlo, "frequency", 2400000000)
        print(f"CLEAN_V2_TX_LISTENING bind={args.bind}:{args.port} tx_uri={uri} frames=24", flush=True)
        conn, addr = listener.accept()
        conn.settimeout(30)
        print(f"CLEAN_V2_RX_CONNECTED peer={addr[0]}:{addr[1]}", flush=True)
        with conn:
            cf = conn.makefile("rwb", buffering=0)
            for item, frame in zip(expected, frames):
                if cf.readline() != b"NEXT\n":
                    raise RuntimeError("RX protocol error before frame")
                current = radio.send(frame * FIXED_SCALE)
                time.sleep(0.08)
                cf.write((json.dumps({"seq": item["seq"]}) + "\n").encode())
                if cf.readline() != b"CAPTURED\n":
                    raise RuntimeError("RX did not acknowledge capture")
                radio.stop(current)
                current = None
                cf.write(b'{"stopped":true}\n')
                print(f"CLEAN_V2_TX_COMPLETE seq={item['seq']} source_index={item['source_index']}", flush=True)
            if cf.readline() != b"NEXT\n":
                raise RuntimeError("RX protocol error at completion")
            cf.write(b'{"done":true}\n')
    finally:
        if current is not None:
            radio.stop(current)
        errors = radio.close()
        listener.close()
        (args.out / "restore.json").write_text(json.dumps(errors, indent=2), encoding="utf-8")
    print(f"CLEAN_V2_TX_DONE result=PASS frames=24 out={args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
