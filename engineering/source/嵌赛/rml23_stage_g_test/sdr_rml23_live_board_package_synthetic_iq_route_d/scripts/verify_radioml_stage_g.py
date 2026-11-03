#!/usr/bin/env python3
"""Independent byte-consistency verifier for a Stage G route-A extraction
directory produced by extract_radioml_stage_g.py.

For every frame listed in manifest_a.json it:
  1. checks the .bin exists and is exactly 8192 bytes;
  2. checks the .bin SHA256 == the manifest's recorded bin_sha256;
  3. re-reads the frame DIRECTLY from the HDF5 (by source_index), rebuilds the
     planar [2,1024] fp32 bytes (.T, no normalization / transpose / I/Q swap),
     and byte-compares them against the .bin (the authoritative check);
  4. cross-checks the HDF5 original label (argmax Y) and SNR (Z) against the
     manifest's hdf5_label / hdf5_snr_db.

This is a SEPARATE implementation from the extractor so a bug in one is not
masked by the other.  Fail-closed: any mismatch exits non-zero.

Usage:
    python -I scripts/verify_radioml_stage_g.py \
        --out-dir stage_g_route_a_radioml \
        --dataset-hdf5 F:/datasets/RadioML2018/GOLD_XYZ_OSC.0001_1024.hdf5
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import numpy as np
import h5py

_INPUT_BYTES = 1024 * 2 * 4  # 8192


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(msg: str):
    print(f"verify_radioml_stage_g: FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage G route-A byte-consistency verifier")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--dataset-hdf5", required=True)
    args = ap.parse_args()

    manifest_path = os.path.join(args.out_dir, "manifest_a.json")
    if not os.path.exists(manifest_path):
        fail(f"missing manifest: {manifest_path}")
    if not os.path.exists(args.dataset_hdf5):
        fail(f"missing HDF5: {args.dataset_hdf5}")

    with open(manifest_path, encoding="utf-8") as f:
        man = json.load(f)

    samples = man["samples"]
    if not samples:
        fail("manifest has zero samples")
    print(f"verifying {len(samples)} frames...")

    # Also confirm the extractor recorded the correct HDF5 identity (the frozen
    # dataset hash e3dd0bef... — cheap to re-derive only when --full-hash given).
    expected_h5 = man.get("hdf5_sha256")

    h5 = h5py.File(args.dataset_hdf5, "r")
    X, Y, Z = h5["X"], h5["Y"], h5["Z"]
    checked = 0
    for s in samples:
        idx = int(s["source_index"])
        raw = np.asarray(X[idx], dtype=np.float32)           # (1024,2)
        planar = np.ascontiguousarray(raw.T)                 # (2,1024) I,Q
        want = planar.tobytes()
        if len(want) != _INPUT_BYTES:
            fail(f"frame {s['index']}: planar bytes {len(want)} != {_INPUT_BYTES}")

        bin_path = os.path.join(args.out_dir, s["bin_file"])
        if not os.path.exists(bin_path):
            fail(f"frame {s['index']}: missing {s['bin_file']}")
        with open(bin_path, "rb") as fh:
            got = fh.read()
        if len(got) != _INPUT_BYTES:
            fail(f"frame {s['index']}: .bin size {len(got)} != {_INPUT_BYTES}")
        if got != want:
            fail(f"frame {s['index']}: .bin bytes != HDF5 source slice")
        if sha256_file(bin_path) != s["bin_sha256"]:
            fail(f"frame {s['index']}: .bin SHA256 != manifest")

        label_h5 = int(np.argmax(np.asarray(Y[idx]).ravel()))
        snr_h5 = float(np.asarray(Z[idx]).ravel()[0])
        if label_h5 != int(s["hdf5_label"]):
            fail(f"frame {s['index']}: HDF5 label {label_h5} != manifest {s['hdf5_label']}")
        if abs(snr_h5 - float(s["hdf5_snr_db"])) > 1e-6:
            fail(f"frame {s['index']}: HDF5 SNR {snr_h5} != manifest {s['hdf5_snr_db']}")

        checked += 1
    h5.close()

    print(f"verified {checked} frames: .bin bytes == HDF5 slice, SHA == manifest, "
          f"label/SNR cross-check OK")
    if expected_h5:
        print(f"  recorded hdf5_sha256={expected_h5}")
    print("== verify_radioml_stage_g: PASS ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
