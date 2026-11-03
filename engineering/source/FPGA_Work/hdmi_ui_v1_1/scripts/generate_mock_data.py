#!/usr/bin/env python3
"""Deterministic mirror of src/mock_data_source.cpp (MockDataSource, V1.1).

Generates mock_data/<scenario>.jsonl for all 10 scenarios, byte-identical across
runs for the same seed, plus mock_data/manifest.json.  Every produced line is a
valid V1.1 ResultFrame per contracts/result_frame_v1_1.schema.json (10 classes,
model-generic).

The ONLY field that differs from the live C++ source is ``timestamp_ns``: the
C++ uses wall-clock ``now_ns()`` (non-deterministic), while this generator emits
a synthetic deterministic value so replay and tests are reproducible.  All other
fields — class, scores, spectrum, latencies, status, counters — match the C++
xorshift32 sequence exactly for the same seed.

The ``stale`` scenario produces 30 healthy frames then (in the live C++ mock
only) goes silent; a finite file cannot encode silence, so replaying its 30
frames and then reaching EOF triggers the same UI-side staleness detector.

Usage:
    python scripts/generate_mock_data.py                 # regenerate all
    python scripts/generate_mock_data.py --scenario normal
    python scripts/generate_mock_data.py --out-dir /tmp/md --seed 7 --fps 15
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys

CONTRACT_VERSION = 2
MODEL_ID = "mock-10class-v1.1"
CLASS_NAMES = [
    "AM-DSB", "WBFM", "2FSK", "GFSK", "BPSK",
    "QPSK", "8PSK", "16QAM", "64QAM", "OFDM",
]

SCENARIOS = [
    "normal",
    "modulation_switch",
    "low_confidence",
    "stale",
    "reorder",
    "drop_overflow",
    "fpga_error",
    "npu_timeout",
    "sdr_disconnect",
    "recovery",
]

# Default frame count per scenario.  The live mock runs until stopped (or, for
# stale/sdr_disconnect, until it self-terminates); these counts fully demonstrate
# each scenario's distinctive behaviour.
DEFAULT_FRAMES = {
    "normal": 200,
    "modulation_switch": 200,
    "low_confidence": 200,
    "stale": 30,           # matches the C++ next() silence point (step >= 30)
    "reorder": 200,
    "drop_overflow": 160,
    "fpga_error": 100,
    "npu_timeout": 100,
    "sdr_disconnect": 31,  # matches the C++ next() end condition (step > 30)
    "recovery": 120,
}

DEFAULT_SEED = 0x20261002
DEFAULT_FPS = 15.0
# Synthetic epoch for timestamp_ns (replaces the C++ wall-clock now_ns()).
BASE_NS = 1700000000000000000

MASK32 = 0xFFFFFFFF


def softmax(v):
    m = max(v)
    ex = [math.exp(x - m) for x in v]
    s = sum(ex)
    return [x / s for x in ex]


def spectrum_for(cls, degraded):
    n = 128
    centre = 18.0 + cls * 12.0
    out = [0.0] * n
    for i in range(n):
        noise = 0.5 + 0.5 * math.sin(i * 12.9898) * math.sin(i * 4.1414)
        v = 0.04 + 0.05 * noise
        d1 = i - centre
        v += (0.4 if degraded else 1.0) * math.exp(-(d1 * d1) / (2.0 * 5.0 * 5.0))
        d2 = i - (centre + 24.0)
        v += 0.25 * math.exp(-(d2 * d2) / (2.0 * 3.0 * 3.0))
        out[i] = v
    return out


class Mock:
    def __init__(self, scenario, seed=DEFAULT_SEED, fps=DEFAULT_FPS):
        self.scenario = scenario
        self.seed = seed
        self.fps = fps
        self.rng = seed & MASK32
        self.frame_id = 0
        self.step = 0

    def rnd(self):
        x = self.rng
        x ^= (x << 13) & MASK32
        x ^= x >> 17
        x ^= (x << 5) & MASK32
        x &= MASK32
        self.rng = x
        return x

    def rnd01(self):
        return (self.rnd() & 0xFFFFFF) / 16777216.0

    def make_frame(self):
        step = self.step
        self.step += 1

        fpga_fault = (self.scenario == "fpga_error" and step >= 30) or (
            self.scenario == "recovery" and 30 <= step < 60
        )
        npu_fault = self.scenario == "npu_timeout" and step >= 30
        degraded = fpga_fault or npu_fault

        # Class selection (index into CLASS_NAMES).
        cls = 7  # 16QAM
        if self.scenario == "modulation_switch":
            cls = [4, 7, 8, 9][(step // 40) % 4]
        elif self.scenario == "low_confidence":
            cls = 5
        elif self.scenario == "stale":
            cls = 7
        elif self.scenario == "reorder":
            cls = 8
        elif self.scenario == "drop_overflow":
            cls = 7
        elif self.scenario == "fpga_error":
            cls = 4
        elif self.scenario == "npu_timeout":
            cls = 6
        elif self.scenario == "sdr_disconnect":
            cls = 2
        elif self.scenario == "recovery":
            cls = 9

        # Frame id / drops / reorder (mirrors the C++ emit logic exactly).
        sequential = self.frame_id
        emit = sequential
        dropped = 0
        overflow = 0
        reorder = 0
        message = ""
        reordered = False
        if self.scenario == "drop_overflow" and step > 0 and step % 50 == 0:
            emit = sequential + 3
            dropped = 3
            overflow = 1
            message = "mock: overflow + dropped frames"
        elif self.scenario == "reorder" and step >= 2 and step % 40 == 20:
            emit = sequential - 2
            reorder = 1
            message = "mock: out-of-order frame_id"
            reordered = True
        frame_id = emit
        self.frame_id = (sequential if reordered else emit) + 1

        sharpness = 4.0
        if self.scenario == "low_confidence":
            sharpness = 0.9
        elif degraded:
            sharpness = 0.6

        logits = [
            (sharpness if i == cls else 0.0) + (self.rnd01() - 0.5) * 0.6
            for i in range(len(CLASS_NAMES))
        ]
        scores = softmax(logits)
        confidence = scores[cls]

        if degraded:
            snr = -4.0 + self.rnd01() * 6.0
        elif self.scenario == "low_confidence":
            snr = 8.0 + self.rnd01() * 4.0
        else:
            snr = 18.0 + self.rnd01() * 6.0

        lat_sdr = 90.0 + self.rnd01() * 20.0
        lat_resample = 25.0 + self.rnd01() * 10.0
        lat_plddr = 40.0 + self.rnd01() * 12.0
        lat_fpga = 0.0 if fpga_fault else (200.0 + self.rnd01() * 40.0)
        lat_npu = 0.0 if npu_fault else (170.0 + self.rnd01() * 30.0)
        end_to_end = lat_sdr + lat_resample + lat_plddr + lat_fpga + lat_npu

        sdr_status = "ok"
        fpga_status = "ok"
        npu_status = "ok"
        timeout = 0
        error = 0

        if self.scenario == "sdr_disconnect" and step >= 30:
            sdr_status = "disconnected"
            message = "mock: SDR link down"
        elif fpga_fault:
            fpga_status = "error"
            error = 1
            message = (
                "mock: faulting (recovery in progress)"
                if self.scenario == "recovery"
                else "mock: FPGA pipeline error"
            )
        elif npu_fault:
            npu_status = "error"
            timeout = 1
            message = "mock: NPU infer timeout"

        spectrum = spectrum_for(cls, degraded)
        timestamp_ns = BASE_NS + step * int(1e9 / self.fps)

        frame = {
            "contract_version": CONTRACT_VERSION,
            "model_id": MODEL_ID,
            "frame_id": frame_id,
            "timestamp_ns": timestamp_ns,
            "source": "MOCK",
            "class_names": list(CLASS_NAMES),
            "scores": scores,
            "predicted_index": cls,
            "predicted_class": CLASS_NAMES[cls],
            "confidence": confidence,
            "snr_db": snr,
            "center_frequency_hz": 2400000000.0,
            "sample_rate_hz": 128000.0,
            "latency_us": {
                "sdr_capture": lat_sdr,
                "resample_frame": lat_resample,
                "plddr_transfer": lat_plddr,
                "fpga_process": lat_fpga,
                "npu_infer": lat_npu,
                "end_to_end": end_to_end,
            },
            "fps": self.fps,
            "counters": {
                "dropped": dropped,
                "overflow": overflow,
                "duplicate": 0,
                "reorder": reorder,
                "timeout": timeout,
                "error": error,
            },
            "sdr_status": sdr_status,
            "fpga_status": fpga_status,
            "npu_status": npu_status,
            "spectrum_bins": spectrum,
        }
        if message:
            frame["message"] = message
        return frame


def _dump(frame):
    # Compact JSON (one object per line), no NaN/Inf is ever emitted.
    return json.dumps(frame, separators=(",", ":"), allow_nan=False)


def generate(scenario, frames, seed, fps):
    m = Mock(scenario, seed=seed, fps=fps)
    lines = []
    for _ in range(frames):
        lines.append(_dump(m.make_frame()))
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Generate mock_data/*.jsonl.")
    ap.add_argument("--out-dir", default=None,
                    help="output directory (default: <project>/mock_data)")
    ap.add_argument("--scenario", default=None, choices=SCENARIOS,
                    help="generate only this scenario (default: all)")
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--fps", type=float, default=DEFAULT_FPS)
    ap.add_argument("--frames", type=int, default=None,
                    help="override the default frame count")
    args = ap.parse_args(argv)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = args.out_dir or os.path.join(root, "mock_data")
    os.makedirs(out_dir, exist_ok=True)

    scenarios = [args.scenario] if args.scenario else SCENARIOS
    manifest = {
        "generator": "scripts/generate_mock_data.py",
        "contract_version": CONTRACT_VERSION,
        "model_id": MODEL_ID,
        "seed": args.seed,
        "fps": args.fps,
        "class_order": CLASS_NAMES,
        "scenarios": [],
    }

    for sc in scenarios:
        frames = args.frames if args.frames is not None else DEFAULT_FRAMES[sc]
        text = generate(sc, frames, args.seed, args.fps)
        path = os.path.join(out_dir, sc + ".jsonl")
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        manifest["scenarios"].append({
            "scenario": sc,
            "file": sc + ".jsonl",
            "frames": frames,
            "sha256": digest,
        })
        print("wrote %s (%d frames, sha256 %s)" % (sc, frames, digest[:16]))

    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=2, sort_keys=True)
        fh.write("\n")
    print("wrote manifest.json")

    return 0


if __name__ == "__main__":
    sys.exit(main())
