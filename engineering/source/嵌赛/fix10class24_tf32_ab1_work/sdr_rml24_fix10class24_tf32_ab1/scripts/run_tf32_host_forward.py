#!/usr/bin/env python3
"""run_tf32_host_forward.py -- Phase B checks 8-9 for the TF32 network.

Runs the TF32 model (model_rml24_tf32/rml24_adamrv11_tf32.{json,raw}) on the
iCraft Host backend N times (default 2) and asserts:
  * exit 0 each time, exactly one ftmp produced, 24*4 bytes (24 raw logits),
  * all 24 logits finite (no NaN/Inf),
  * every forward is BYTE-IDENTICAL (determinism),
  * argmax is stable across forwards (implied by byte-identity).

Input tensor is [1,2,1024] fp32 = 8192 bytes f32le.  By default a deterministic
synthetic IQ is written; pass --input-bin to use a real exported model input.

Pure stdlib (no numpy).  API-only: never touches board/NPU.  Uses the
space-free icraft copy because the Host backend fails on the "CLI v3.39.0"
space path.

  python -I scripts/run_tf32_host_forward.py \
      --icraft-run D:/icraft/bin/icraft-run.exe --n-forward 3
"""
from __future__ import annotations

import argparse
import hashlib
import math
import shutil
import struct
import subprocess
import sys
from pathlib import Path

NETWORK_NAME = "model_24class"
EXPECT_CLASS_COUNT = 24
EXPECT_INPUT_FLOATS = 2 * 1024


def fail(msg: str) -> None:
    print("FAIL: %s" % msg, file=sys.stderr)
    sys.exit(1)


def synthetic_input_bin() -> bytes:
    """Deterministic [2,1024] fp32: I = sin, Q = cos at a fixed tone."""
    out = []
    for i in range(1024):
        ph = 2.0 * math.pi * (0.03125) * i
        out.append(math.sin(ph) * 0.5)   # I
        out.append(math.cos(ph) * 0.5)   # Q
    return struct.pack("<%df" % len(out), *out)


def run_one(icraft_run: Path, model_json: Path, model_raw: Path,
            input_bin: Path, log_path: Path) -> tuple[bytes, str]:
    if log_path.exists():
        shutil.rmtree(log_path)
    log_path.mkdir(parents=True)
    cmd = [
        str(icraft_run),
        "--json", str(model_json),
        "--raw", str(model_raw),
        "--network", NETWORK_NAME,
        "--input", str(input_bin),
        "--backends", "Host",
        "--dump_output",
        "--log_path", str(log_path),
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        fail("icraft-run exit %d\nstdout: %s\nstderr: %s"
             % (proc.returncode,
                proc.stdout.decode("utf-8", "replace")[-1500:],
                proc.stderr.decode("utf-8", "replace")[-2000:]))
    ftmp_dir = log_path / NETWORK_NAME / "ftmpHQB"
    ftmps = list(ftmp_dir.glob("*.ftmp")) if ftmp_dir.is_dir() else []
    if len(ftmps) != 1:
        fail("expected exactly 1 ftmp under %s, got %d" % (ftmp_dir, len(ftmps)))
    raw = ftmps[0].read_bytes()
    if len(raw) != EXPECT_CLASS_COUNT * 4:
        fail("ftmp %s is %d bytes (want %d)" % (ftmps[0].name, len(raw), EXPECT_CLASS_COUNT * 4))
    return raw, hashlib.sha256(raw).hexdigest()


def main(argv) -> int:
    ap = argparse.ArgumentParser(description="TF32 Host forward determinism check")
    ap.add_argument("--model-dir", default="model_rml24_tf32")
    ap.add_argument("--icraft-run", default="D:/icraft/bin/icraft-run.exe")
    ap.add_argument("--input-bin", default=None)
    ap.add_argument("--n-forward", type=int, default=2)
    ap.add_argument("--workdir", default="host_forward_check")
    args = ap.parse_args(argv)

    icraft_run = Path(args.icraft_run)
    if not icraft_run.is_file():
        fail("icraft-run.exe not found: %s" % icraft_run)
    model_dir = Path(args.model_dir)
    model_json = model_dir / "rml24_adamrv11_tf32.json"
    model_raw = model_dir / "rml24_adamrv11_tf32.raw"
    if not model_json.is_file() or not model_raw.is_file():
        fail("tf32 json/raw not found under %s" % model_dir)

    workdir = Path(args.workdir)
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)

    if args.input_bin:
        input_bin = Path(args.input_bin)
        if not input_bin.is_file():
            fail("--input-bin not found: %s" % input_bin)
        data = input_bin.read_bytes()
        if len(data) != EXPECT_INPUT_FLOATS * 4:
            fail("input bin %s is %d bytes (want %d)" % (input_bin, len(data), EXPECT_INPUT_FLOATS * 4))
    else:
        input_bin = workdir / "input_synthetic_f32le.bin"
        input_bin.write_bytes(synthetic_input_bin())
        data = input_bin.read_bytes()
    print("[host-forward] input %s (%d bytes, %d floats)"
          % (input_bin.name, len(data), EXPECT_INPUT_FLOATS))
    print("[host-forward] model_json_sha=%s" % hashlib.sha256(model_json.read_bytes()).hexdigest())
    print("[host-forward] model_raw_sha =%s" % hashlib.sha256(model_raw.read_bytes()).hexdigest())

    n = args.n_forward
    if n < 2:
        fail("--n-forward must be >= 2")
    raw_list, digests, argmaxes = [], [], []
    for k in range(n):
        raw, digest = run_one(icraft_run, model_json, model_raw, input_bin,
                              workdir / ("logs_run%d" % (k + 1)))
        logits = struct.unpack("<%df" % EXPECT_CLASS_COUNT, raw)
        if not all(math.isfinite(x) for x in logits):
            fail("forward %d produced non-finite logits: %s" % (k + 1, logits))
        argmax = max(range(EXPECT_CLASS_COUNT), key=lambda i: logits[i])
        raw_list.append(raw)
        digests.append(digest)
        argmaxes.append(argmax)
        print("[host-forward] run%d: 24 logits finite, argmax=%d, ftmp_sha256=%s"
              % (k + 1, argmax, digest))

    if len(set(digests)) != 1:
        fail("forwards are NOT byte-identical: %s" % digests)
    if len(set(argmaxes)) != 1:
        fail("argmax differs across forwards: %s" % argmaxes)
    print("[host-forward] PASS: %d forwards byte-identical (ftmp sha %s), argmax=%d"
          % (n, digests[0], argmaxes[0]))
    print("[host-forward] logits[0]=%s"
          % (struct.unpack("<%df" % EXPECT_CLASS_COUNT, raw_list[0]),))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
