#!/usr/bin/env python3
"""Stage G route-A prerequisite: extract INDEPENDENT RadioML2018.01A test frames
to board-consumable [2,1024] fp32 .bin files + a manifest.

This is NOT a model-evaluation set and NOT the conformance golden: it uses the
FROZEN test split (rml24_split_indices.npz test_indices), never the 240-frame
deployment_golden validation subset (red line 7).

Byte contract (identical to deployment_golden/input_N.bin and to the board NPU
input): X[hdf5_idx] (1024,2) -> .T (2,1024) planar, plane0=I / plane1=Q -> 8192
bytes fp32 little-endian, NO normalization, NO transpose beyond .T, NO I/Q swap,
NO byte mutation.  After each write the .bin is re-read and byte-compared against
the HDF5 source slice.

The board A-route reads the produced directory (--radioml-bin-dir) and fail-closes
on missing manifest / SHA mismatch / label mismatch / size != 8192.

Usage:
    python scripts/extract_radioml_stage_g.py \
        --dataset-hdf5 F:/datasets/RadioML2018/GOLD_XYZ_OSC.0001_1024.hdf5 \
        --split-npz F:/FPGA_Work/sdr_amr_rml24_ood_v1_1/data/radioml2018/rml24_split_indices.npz \
        --classes BPSK,QPSK,4ASK,16QAM \
        --snr-db 20,22,24,26,28,30 \
        --count 500 --out-dir <dir>

Exit 0 on success; non-zero on any identity / cross-check / byte-consistency
failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import numpy as np
import h5py

# Frozen 24-class source order (== cat::target_24).  The classes route A tests.
SOURCE_CLASS_INDEX = {
    "OOK": 0, "4ASK": 1, "8ASK": 2, "BPSK": 3, "QPSK": 4, "8PSK": 5,
    "16PSK": 6, "32PSK": 7, "16APSK": 8, "32APSK": 9, "64APSK": 10,
    "128APSK": 11, "16QAM": 12, "32QAM": 13, "64QAM": 14, "128QAM": 15,
    "256QAM": 16, "AM-SSB-WC": 17, "AM-SSB-SC": 18, "AM-DSB-WC": 19,
    "AM-DSB-SC": 20, "FM": 21, "GMSK": 22, "OQPSK": 23,
}
INDEX_TO_CLASS = {v: k for k, v in SOURCE_CLASS_INDEX.items()}

_INPUT_SAMPLES = 1024
_INPUT_PLANES = 2
_INPUT_BYTES = _INPUT_SAMPLES * _INPUT_PLANES * 4  # 8192


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def fail(msg: str):
    print(f"extract_radioml_stage_g: FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage G route-A RadioML test-frame extraction")
    ap.add_argument("--dataset-hdf5", required=True)
    ap.add_argument("--split-npz", required=True)
    ap.add_argument("--classes", default="BPSK,QPSK,4ASK,16QAM")
    ap.add_argument("--snr-db", default="20,22,24,26,28,30")
    ap.add_argument("--count", type=int, default=500)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    for p in (args.dataset_hdf5, args.split_npz):
        if not os.path.exists(p):
            fail(f"missing input path: {p}")

    classes = [c.strip() for c in args.classes.split(",") if c.strip()]
    for c in classes:
        if c not in SOURCE_CLASS_INDEX:
            fail(f"unknown class {c!r}; allowed: {sorted(SOURCE_CLASS_INDEX)}")
    class_indices = [SOURCE_CLASS_INDEX[c] for c in classes]

    snr_values = [float(x) for x in args.snr_db.split(",") if x.strip()]
    if not snr_values:
        fail("empty --snr-db")

    if args.count < 1:
        fail("--count must be >= 1")

    os.makedirs(args.out_dir, exist_ok=True)

    # --- identity hashes (streaming, recorded verbatim in the manifest) --------
    print("hashing HDF5 (21.4 GiB, one streaming pass)...")
    hdf5_sha = sha256_file(args.dataset_hdf5)
    split_sha = sha256_file(args.split_npz)
    print(f"  hdf5_sha256={hdf5_sha}")
    print(f"  split_npz_sha256={split_sha}")

    # --- load frozen test split (scalar labels + SNR) --------------------------
    with np.load(args.split_npz, allow_pickle=False) as z:
        test_indices = z["test_indices"].astype(np.int64)
        test_labels = z["test_labels"].astype(np.int64)
        test_snrs = z["test_snrs"].astype(np.float32)
    if not (test_indices.shape == test_labels.shape == test_snrs.shape):
        fail(f"test split shape mismatch: {test_indices.shape} {test_labels.shape} {test_snrs.shape}")

    # --- deterministic selection: per class, spread across the SNR values ------
    # The HDF5 is SNR-major ordered, so a plain ascending-row-id sort would
    # collapse every class's selection onto the lowest SNR.  Instead, for each
    # class distribute `count` frames evenly across the (ascending) SNR values,
    # ascending HDF5 row id within each SNR; the remainder goes to the lowest SNRs.
    snr_values = sorted(snr_values)
    q, rem = divmod(args.count, len(snr_values))   # frames per SNR, remainder
    frames_per_snr = [q + (1 if si < rem else 0) for si in range(len(snr_values))]
    selected = []  # (test_position, hdf5_row, class_idx)
    for ci in class_indices:
        for si, snr in enumerate(snr_values):
            take = frames_per_snr[si]
            pos = [k for k in range(len(test_labels))
                   if int(test_labels[k]) == ci and abs(float(test_snrs[k]) - snr) < 1e-5]
            pos.sort(key=lambda k: int(test_indices[k]))  # ascending HDF5 row id
            if len(pos) < take:
                fail(f"class {INDEX_TO_CLASS[ci]} @ {snr:g} dB: only {len(pos)} "
                     f"test frames, requested {take}")
            selected.extend((int(k), int(test_indices[k]), ci) for k in pos[:take])

    print(f"selected {len(selected)} frames "
          f"({len(class_indices)} classes x {args.count}, "
          f"spread over SNR {snr_values})")

    # --- extract + byte-verify -------------------------------------------------
    samples = []
    with h5py.File(args.dataset_hdf5, "r") as f:
        X = f["X"]
        Y = f["Y"]
        Z = f["Z"]
        for out_idx, (test_pos, hdf5_idx, ci) in enumerate(selected):
            raw = np.asarray(X[hdf5_idx], dtype=np.float32)          # (1024,2)
            planar = np.ascontiguousarray(raw.T)                      # (2,1024) I,Q
            if planar.size != _INPUT_PLANES * _INPUT_SAMPLES:
                fail(f"frame {out_idx}: planar size {planar.size}")
            planar_bytes = planar.tobytes()
            if len(planar_bytes) != _INPUT_BYTES:
                fail(f"frame {out_idx}: planar bytes {len(planar_bytes)}")

            # Cross-check HDF5 original label/SNR vs the frozen test split (fail-closed).
            label_h5 = int(np.argmax(np.asarray(Y[hdf5_idx]).ravel()))
            snr_h5 = float(np.asarray(Z[hdf5_idx]).ravel()[0])
            if label_h5 != int(test_labels[test_pos]):
                fail(f"frame {out_idx}: HDF5 label {label_h5} != test split label "
                     f"{int(test_labels[test_pos])}")
            if abs(snr_h5 - float(test_snrs[test_pos])) > 1e-6:
                fail(f"frame {out_idx}: HDF5 SNR {snr_h5} != test split SNR "
                     f"{float(test_snrs[test_pos])}")
            if label_h5 != ci:
                fail(f"frame {out_idx}: label {label_h5} != requested class {ci}")

            bin_name = f"input_{out_idx:04d}.bin"
            bin_path = os.path.join(args.out_dir, bin_name)
            with open(bin_path, "wb") as fh:
                fh.write(planar_bytes)

            # byte-consistency: re-read and compare with the HDF5 source slice.
            with open(bin_path, "rb") as fh:
                reread = fh.read()
            if reread != planar_bytes:
                fail(f"frame {out_idx}: re-read .bin bytes != HDF5 source slice")
            if len(reread) != _INPUT_BYTES:
                fail(f"frame {out_idx}: .bin size {len(reread)} != {_INPUT_BYTES}")

            samples.append({
                "index": out_idx,
                "source_index": hdf5_idx,           # HDF5 row id (test_indices value)
                "hdf5_label": label_h5,
                "hdf5_snr_db": snr_h5,
                "class_index": ci,
                "class_name": INDEX_TO_CLASS[ci],
                "bin_file": bin_name,
                "bin_sha256": sha256_bytes(planar_bytes),
            })

    # --- manifest (board reads the TSV; JSON is full provenance) ---------------
    with open(os.path.join(args.out_dir, "manifest_a.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump({
            "route": "A",
            "purpose": "independent RadioML2018.01A test frames (frozen test split), "
                       "NOT the deployment_golden validation subset",
            "hdf5_sha256": hdf5_sha,
            "split_npz_sha256": split_sha,
            "classes": class_indices,
            "snr_db": snr_values,
            "count_per_class": args.count,
            "frames_per_snr": frames_per_snr,
            "num_samples": len(samples),
            "input_shape": [1, _INPUT_PLANES, _INPUT_SAMPLES],
            "input_dtype": "float32",
            "input_bytes_per_frame": _INPUT_BYTES,
            "input_layout": "planar I/Q: plane0=I (first 1024), plane1=Q (next 1024)",
            "normalization": "none (HDF5 clean-signal complex RMS already 1.0)",
            "sample_rate_hz": 128000,
            "samples": samples,
        }, fh, indent=2)

    # Board-parsable TSV: index \t source_index \t hdf5_label \t snr_db \t
    #                     class_index \t class_name \t bin_file \t bin_sha256
    with open(os.path.join(args.out_dir, "manifest_a.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        for s in samples:
            fh.write(f"{s['index']}\t{s['source_index']}\t{s['hdf5_label']}\t"
                     f"{s['hdf5_snr_db']:.1f}\t{s['class_index']}\t{s['class_name']}\t"
                     f"{s['bin_file']}\t{s['bin_sha256']}\n")

    print(f"wrote {len(samples)} .bin files + manifest_a.json/tsv to {args.out_dir}")
    print("== extract_radioml_stage_g: PASS ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
