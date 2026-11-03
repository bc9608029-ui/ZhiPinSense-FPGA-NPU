#!/usr/bin/env python3
"""M29 Phase F5 -- regenerate ``deployment_golden/`` as a RML23 *conformance* golden.

This is NOT an accuracy evaluation set.  It is a deployment-consistency golden:
240 deterministic input frames (24 source classes x 10), each paired with the
FROZEN expA_bf16_head model's own merged-23 argmax, so the board's offline gate
(``run_gate9_rml23.sh --phase=offline``) proves the board NPU -> AM-SSB merge ->
UI link reproduces the frozen host reference.  A mismatch means a deployment
contract break (wrong model / label order / merge / input layout), never that the
model is "inaccurate".  Do not read the offline match_rate as model accuracy.

Determinism / anti-picking guarantees:
  * Sampling is fully deterministic and reproducible: for each source class, the
    subset positions are ordered by ascending ``sub_indices`` (the HDF5 row id, a
    unique total order; the position ``p`` is the tie-break) and the first 10 are
    taken.  No RNG, no reference to the board's output, no per-frame rejection.
  * The whole 1536-frame merge is hard-asserted against the frozen cross-language
    reference (``board_rml23/test_data/expA_pred23_ref_i32.bin`` and friends)
    before anything is written -- any divergence aborts non-zero.

Fail-closed identity verification (Phase 0) runs first and aborts on any mismatch.

Input contract (identical to the board NPU input and to the eval pipeline that
produced expA_logits.npy -- ``scripts/exp_quant_eval_m29.py``):
    X[hdf5_idx] (1024,2) -> .T (2,1024) planar, plane0=I, plane1=Q -> 8192 bytes
    fp32, NO further normalization (the HDF5 clean-signal complex RMS is already
    1.0).  Sample rate 128000 Hz.  Input tensor shape [1,2,1024].

Usage:
    python -I scripts/gen_rml23_golden.py [--out deployment_golden] \
        [--model-json ...] [--model-raw ...] [--expA-logits ...] \
        [--subset ...] [--hdf5 ...] [--ref-dir ...]

Exit 0 on success; non-zero on any identity mismatch, cross-language divergence,
or write error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys

# --- frozen identities (M29 Phase F5, cross-checked on host) -----------------
MODEL_JSON_SHA256 = "d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d"
MODEL_RAW_SHA256 = "2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba"
PARAMS_MD5 = "7966a4829fc713b2e8ea6c04168be263"
EXPALOGITS_SHA256 = "6a076cace973d6bf2376c39fac66af7f642cd3b4a414374250662e3217e09fbb"
SUBSET_SHA256 = "49668c731cb8186d2eb488f3d0a0865406cf9c5e65d97012d56f741973d5b53b"
HDF5_SHA256 = "e3dd0bef66a3426959ee66a1709a8c0a95d4f8395d18aaf6f1214bdbc763bd38"
SOURCE_LABEL_SHA256 = "3e1382d1242a206dae3f73535deba30b461e8573889b60004db9d2ce055fa549"
DEPLOYED_LABEL_SHA256 = "15072cd29538b08bc53f4e59237994297d71d5eb44d499413f9bb08929459c88"
MERGED_CONTRACT_SHA256 = "f9f7f3812ace1ec523c810408a31c6fc12b979d7d62900b90924cabf08bebb1e"

_SUBSET_SIZE = 1536
_PER_CLASS = 10
_SOURCE_CLASSES = 24
_DEPLOYED_CLASSES = 23
_INPUT_SAMPLES = 1024
_INPUT_PLANES = 2
_INPUT_BYTES = _INPUT_SAMPLES * _INPUT_PLANES * 4  # 8192


def _dirs():
    script = os.path.dirname(os.path.abspath(__file__))   # .../board_rml23_live/scripts
    board_live = os.path.dirname(script)                  # .../board_rml23_live
    m29 = os.path.dirname(board_live)                     # .../sdr_rml24_npu_deployment_m29
    return script, board_live, m29


_SCRIPT, _BOARD_LIVE, _M29 = _dirs()

# The canonical merge/contract modules (stdlib + numpy, importable under -I).
sys.path.insert(0, os.path.join(_M29, "postprocess"))
sys.path.insert(0, os.path.join(_M29, "contracts"))

from rml23_merged import merge_many_24_to_23  # noqa: E402
from rml23_merged_contract import (  # noqa: E402
    AMSSB_DEPLOYED_INDEX,
    AMSSB_SOURCE_SC,
    AMSSB_SOURCE_WC,
    DEPLOYED_CLASS_COUNT,
    DEPLOYED_LABEL_ORDER_23,
    NPU_OUTPUT_DIM,
    SOURCE_CLASS_COUNT,
    SOURCE_LABEL_ORDER_24,
    SOURCE_TO_DEPLOYED,
    assert_23class_contract_consistent,
    label_order_23_sha256,
    merged_contract_sha256,
    source_label_order_sha256,
)

import numpy as np  # noqa: E402


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def fail(msg: str):
    print(f"gen_rml23_golden: FAIL: {msg}", file=sys.stderr)
    sys.exit(1)


def softmax(logits) -> list:
    a = [float(v) for v in logits]
    m = max(a)
    e = [math.exp(v - m) for v in a]
    s = sum(e)
    return [v / s for v in e]


def verify_identity(args) -> None:
    """Phase 0: fail-closed frozen identity verification."""
    print("== Phase 0: frozen identity verification ==")
    checks = []

    def chk(name, actual, expected):
        ok = actual == expected
        checks.append((name, ok))
        print(f"  {'OK ' if ok else 'BAD'} {name} = {actual}")
        if not ok:
            fail(f"{name} mismatch: got {actual}, expected {expected}")

    chk("model json SHA256", sha256_file(args.model_json), MODEL_JSON_SHA256)
    chk("model raw  SHA256", sha256_file(args.model_raw), MODEL_RAW_SHA256)

    with open(args.model_json, "r", encoding="utf-8") as f:
        mj = json.load(f)
    chk("params_md5", mj.get("params_md5"), PARAMS_MD5)
    chk("params_bytes", mj.get("params_bytes"), os.path.getsize(args.model_raw))

    chk("expA_logits.npy SHA256", sha256_file(args.expA_logits), EXPALOGITS_SHA256)
    chk("subset_index.npz SHA256", sha256_file(args.subset), SUBSET_SHA256)
    print(f"  ... hashing HDF5 (21.4 GiB, one streaming pass; this is the slow step)")
    chk("HDF5 SHA256", sha256_file(args.hdf5), HDF5_SHA256)

    # Contract SHAs (recomputed from the imported contract module itself).
    chk("source 24-class label SHA", source_label_order_sha256(SOURCE_LABEL_ORDER_24),
        SOURCE_LABEL_SHA256)
    chk("deployed 23-class label SHA", label_order_23_sha256(), DEPLOYED_LABEL_SHA256)
    chk("merged contract SHA", merged_contract_sha256(), MERGED_CONTRACT_SHA256)

    assert_23class_contract_consistent()
    print(f"  OK  contract internally consistent "
          f"(AM-SSB WC={AMSSB_SOURCE_WC} SC={AMSSB_SOURCE_SC} -> deployed {AMSSB_DEPLOYED_INDEX})")
    print("== Phase 0 PASS ==")


def load_and_assert_reference(args):
    """Load expA logits + subset, and hard-assert the 1536-frame merge against the
    frozen cross-language reference.  Returns (logits24, merged32, pred23, sub_indices,
    sub_labels, sub_snrs)."""
    import h5py  # noqa: F401  (h5py only needed later for reading rows; keep import here)

    logits24 = np.load(args.expA_logits)
    if logits24.shape != (_SUBSET_SIZE, NPU_OUTPUT_DIM) or logits24.dtype != np.float32:
        fail(f"expA_logits.npy shape/dtype unexpected: {logits24.shape} {logits24.dtype}")

    with np.load(args.subset, allow_pickle=False) as z:
        sub_indices = z["sub_indices"].astype(np.int64)
        sub_labels = z["sub_labels"].astype(np.int64)
        sub_snrs = z["sub_snrs"].astype(np.float32)
    if sub_indices.shape != (_SUBSET_SIZE,) or sub_labels.shape != (_SUBSET_SIZE,):
        fail(f"subset shape unexpected: indices {sub_indices.shape} labels {sub_labels.shape}")

    import collections
    counts = collections.Counter(int(x) for x in sub_labels)
    if set(counts.keys()) != set(range(_SOURCE_CLASSES)) or any(v != 64 for v in counts.values()):
        fail(f"subset per-class counts not 64x24: {sorted(counts.items())}")

    # Cross-language hard assertion: merged 23-class argmax == frozen pred23_ref.
    merged = merge_many_24_to_23(logits24)            # (1536, 23) float64
    merged32 = merged.astype(np.float32)
    pred23 = merged32.argmax(axis=1).astype(np.int32)
    raw24_top1 = logits24.argmax(axis=1).astype(np.int32)

    ref = os.path.join(args.ref_dir, "")
    pred_ref = np.fromfile(ref + "expA_pred23_ref_i32.bin", dtype=np.int32)
    raw_ref = np.fromfile(ref + "expA_raw24_top1_ref_i32.bin", dtype=np.int32)
    merged_ref = np.fromfile(ref + "expA_merged_1536x23_f32.bin",
                             dtype=np.float32).reshape(_SUBSET_SIZE, 23)
    logits_ref = np.fromfile(ref + "expA_logits_1536x24_f32.bin",
                             dtype=np.float32).reshape(_SUBSET_SIZE, 24)

    if pred_ref.shape != (_SUBSET_SIZE,) or raw_ref.shape != (_SUBSET_SIZE,):
        fail("frozen reference .bin size mismatch")

    def assert_all_equal(name, a, b, tol=0.0):
        diff = np.abs(a.astype(np.float64) - b.astype(np.float64))
        bad = int((diff > tol).sum())
        print(f"  {'OK ' if bad == 0 else 'BAD'} {name}: mismatch={bad} "
              f"max_abs_diff={float(diff.max()):.6g}")
        if bad != 0:
            fail(f"{name} diverged from frozen reference ({bad} mismatches)")

    assert_all_equal("logits24 vs frozen expA_logits_1536x24_f32.bin", logits24, logits_ref)
    assert_all_equal("merged23 vs frozen expA_merged_1536x23_f32.bin", merged32, merged_ref)
    assert_all_equal("merged argmax vs expA_pred23_ref_i32.bin", pred23, pred_ref)
    assert_all_equal("raw24 top1 vs expA_raw24_top1_ref_i32.bin", raw24_top1, raw_ref)
    print("== cross-language reference assertion PASS (1536/1536) ==")
    return logits24, merged32, pred23, sub_indices, sub_labels, sub_snrs


def select_main_set(sub_indices, sub_labels):
    """Deterministic 24x10 selection.  Returns list of subset positions (len 240)."""
    positions_by_class = [[] for _ in range(_SOURCE_CLASSES)]
    for p in range(_SUBSET_SIZE):
        positions_by_class[int(sub_labels[p])].append(p)
    for c in range(_SOURCE_CLASSES):
        # total order: sub_indices ascending, then position ascending (tie-break).
        positions_by_class[c].sort(key=lambda p: (int(sub_indices[p]), p))
    selected = []
    for c in range(_SOURCE_CLASSES):
        selected.extend(positions_by_class[c][:_PER_CLASS])
    assert len(selected) == _SOURCE_CLASSES * _PER_CLASS
    # BPSK (source 3) and QPSK (source 4) must each contribute exactly 10.
    for c in (3, 4):
        n = sum(1 for p in selected if int(sub_labels[p]) == c)
        assert n == _PER_CLASS, f"source class {c} must have {_PER_CLASS} frames, got {n}"
    return selected


def write_golden(args, selected, logits24, merged32, pred23,
                 sub_indices, sub_labels, sub_snrs) -> None:
    import h5py

    out_dir = args.out
    os.makedirs(out_dir, exist_ok=True)

    # Clear any stale 12-class files in the target golden dir (deployment_golden is
    # exclusively owned by this generator).
    for name in os.listdir(out_dir):
        p = os.path.join(out_dir, name)
        if os.path.isfile(p):
            os.remove(p)

    tsv_lines = []
    logits_lines = []
    samples = []
    covered = set()

    with h5py.File(args.hdf5, "r") as f:
        X = f["X"]
        for out_idx, p in enumerate(selected):
            hdf5_idx = int(sub_indices[p])
            src_class = int(sub_labels[p])
            raw = np.asarray(X[hdf5_idx], dtype=np.float32)          # (1024,2)
            planar = np.ascontiguousarray(raw.T)                      # (2,1024) I,Q
            if planar.size != _INPUT_PLANES * _INPUT_SAMPLES:
                fail(f"frame {out_idx}: unexpected planar size {planar.size}")
            in_path = os.path.join(out_dir, f"input_{out_idx:03d}.bin")
            planar.tofile(in_path)
            if os.path.getsize(in_path) != _INPUT_BYTES:
                fail(f"frame {out_idx}: input file not {_INPUT_BYTES} bytes")

            l24 = logits24[p].astype(np.float32)                      # 24-dim raw
            m23 = merged32[p].astype(np.float32)                      # 23-dim merged
            argmax23 = int(pred23[p])
            argmax_class = DEPLOYED_LABEL_ORDER_23[argmax23]
            prob = softmax(m23)
            confidence = prob[argmax23]

            # item-5 self-check: label is the contract label for the argmax index.
            if argmax_class != DEPLOYED_LABEL_ORDER_23[argmax23]:
                fail(f"frame {out_idx}: argmax_class != label_order_23[argmax]")
            if not (0 <= argmax23 < _DEPLOYED_CLASSES):
                fail(f"frame {out_idx}: argmax out of range {argmax23}")
            if not (0.0 <= confidence <= 1.0):
                fail(f"frame {out_idx}: confidence out of range {confidence}")
            if abs(sum(prob) - 1.0) > 1e-6:
                fail(f"frame {out_idx}: softmax sum != 1.0")

            covered.add(argmax23)

            tsv_lines.append(f"{out_idx}\t{argmax23}\t{src_class}\t{argmax_class}\t{confidence:.6f}\n")
            logits_line = "\t".join([str(out_idx)] + [repr(float(x)) for x in m23])
            logits_lines.append(logits_line + "\n")
            samples.append({
                "index": out_idx,
                "subset_position": p,
                "hdf5_index": hdf5_idx,
                "source_label": SOURCE_LABEL_ORDER_24[src_class],
                "source_class": src_class,
                "snr_db": float(sub_snrs[p]),
                "input_file": f"input_{out_idx:03d}.bin",
                "merged23_argmax": argmax23,
                "argmax_class_23": argmax_class,
                "confidence": confidence,
                "raw_24_logits": [float(x) for x in l24],
                "merged_23_logits": [float(x) for x in m23],
            })

    # --- expected_argmax.tsv (board reads f[1] as the expected merged argmax) ---
    with open(os.path.join(out_dir, "expected_argmax.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(tsv_lines)

    # --- expected_logits.tsv (provenance; the RML23 runtime never reads it) ----
    with open(os.path.join(out_dir, "expected_logits.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(logits_lines)

    # --- expected_logits_or_argmax.json (provenance) ---------------------------
    provenance = {
        "golden_kind": "conformance",
        "description": ("deployment-consistency golden: expected argmax = the frozen "
                        "expA_bf16_head model's own merged-23 output, NOT ground-truth "
                        "labels.  match_rate is deployment consistency, never accuracy."),
        "model_json_sha256": MODEL_JSON_SHA256,
        "model_raw_sha256": MODEL_RAW_SHA256,
        "params_md5": PARAMS_MD5,
        "expA_logits_npy_sha256": EXPALOGITS_SHA256,
        "subset_npz_sha256": SUBSET_SHA256,
        "hdf5_sha256": HDF5_SHA256,
        "source_label_sha256": SOURCE_LABEL_SHA256,
        "deployed_label_sha256": DEPLOYED_LABEL_SHA256,
        "merged_contract_sha256": MERGED_CONTRACT_SHA256,
        "class_order_24": list(SOURCE_LABEL_ORDER_24),
        "class_order_23": list(DEPLOYED_LABEL_ORDER_23),
        "source_to_deployed": list(SOURCE_TO_DEPLOYED),
        "merge_algorithm": "logaddexp",
        "input_shape": [1, _INPUT_PLANES, _INPUT_SAMPLES],
        "input_dtype": "float32",
        "input_bytes_per_frame": _INPUT_BYTES,
        "input_layout": "planar I/Q: plane0=I (first 1024), plane1=Q (next 1024)",
        "normalization": "none_rms_already_1.0",
        "sample_rate_hz": 128000,
        "expected_file": "expected_argmax.tsv",
        "expected_column_1_is": "merged23_argmax (0..22)",
        "samples": samples,
    }
    with open(os.path.join(out_dir, "expected_logits_or_argmax.json"), "w",
              encoding="utf-8", newline="\n") as fh:
        json.dump(provenance, fh, indent=2)

    # --- manifest.json (sampling algorithm + identity, fully deterministic) ----
    manifest = {
        "golden_kind": "conformance",
        "sampling_strategy": "B",
        "num_samples": len(selected),
        "per_source_class": _PER_CLASS,
        "source_classes": _SOURCE_CLASSES,
        "deployed_classes": _DEPLOYED_CLASSES,
        "sampling_algorithm": (
            "deterministic, reproducible: for each source class 0..23, sort the "
            "subset positions by ascending sub_indices (HDF5 row id; unique total "
            "order, tie-break = subset position), take the first 10.  No RNG, no "
            "reference to board output, no per-frame rejection."
        ),
        "source_classes_covered": list(range(_SOURCE_CLASSES)),
        "includes_bpsk_qpsk": {"BPSK_source_class": 3, "QPSK_source_class": 4,
                               "frames_each": _PER_CLASS},
        "model_json_sha256": MODEL_JSON_SHA256,
        "model_raw_sha256": MODEL_RAW_SHA256,
        "params_md5": PARAMS_MD5,
        "expA_logits_npy_sha256": EXPALOGITS_SHA256,
        "subset_npz_sha256": SUBSET_SHA256,
        "hdf5_sha256": HDF5_SHA256,
        "source_label_sha256": SOURCE_LABEL_SHA256,
        "deployed_label_sha256": DEPLOYED_LABEL_SHA256,
        "merged_contract_sha256": MERGED_CONTRACT_SHA256,
        "input_shape": [1, _INPUT_PLANES, _INPUT_SAMPLES],
        "input_dtype": "float32",
        "input_bytes_per_frame": _INPUT_BYTES,
        "normalization": "none_rms_already_1.0",
        "sample_rate_hz": 128000,
        "expected_file": "expected_argmax.tsv",
        "expected_column_1_is": "merged23_argmax (0..22)",
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=2)

    # --- coverage report + optional supplemental (audit only, board never reads) ---
    missing = [m for m in range(_DEPLOYED_CLASSES) if m not in covered]
    coverage = {
        "main_set_num_samples": len(selected),
        "expected_deployed_argmax_covered": sorted(covered),
        "expected_deployed_argmax_missing": missing,
        "all_23_deployed_classes_covered": len(missing) == 0,
        "note": ("coverage audit of the model's own predictions over the main 240; "
                 "NOT a gate.  A missing class simply means the model did not predict "
                 "it top-1 in these 240 frames -- the conformance gate only checks "
                 "board-vs-reference agreement, not class coverage."),
    }
    with open(os.path.join(out_dir, "coverage_report.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(coverage, fh, indent=2)

    if missing:
        write_coverage_supplemental(args, selected, missing, logits24, merged32,
                                    pred23, sub_indices, sub_labels, sub_snrs)

    print(f"  wrote {len(selected)} input frames + expected_argmax.tsv "
          f"({len(selected)} lines) to {out_dir}")
    print(f"  expected deployed-argmax coverage: {sorted(covered)}")
    print(f"  missing deployed classes: {missing if missing else '(none -- all 23 covered)'}")


def write_coverage_supplemental(args, selected, missing, logits24, merged32, pred23,
                                sub_indices, sub_labels, sub_snrs) -> None:
    """Deterministic coverage audit supplement for deployed classes the main set's
    expected argmax never hits.  Independent dir, own manifest, board gate NEVER
    reads it.  Never alters the main 24x10 set."""
    import h5py

    sup_dir = os.path.join(args.out, "coverage_supplemental")
    os.makedirs(sup_dir, exist_ok=True)
    for name in os.listdir(sup_dir):
        p = os.path.join(sup_dir, name)
        if os.path.isfile(p):
            os.remove(p)

    main_positions = set(selected)
    k_per_missing = 5
    rows = []
    for m in missing:
        cand = [p for p in range(_SUBSET_SIZE)
                if p not in main_positions and int(pred23[p]) == m]
        cand.sort(key=lambda p: (int(sub_indices[p]), p))
        rows.extend(cand[:k_per_missing])

    tsv_lines = []
    samples = []
    with h5py.File(args.hdf5, "r") as f:
        X = f["X"]
        for out_idx, p in enumerate(rows):
            hdf5_idx = int(sub_indices[p])
            src_class = int(sub_labels[p])
            planar = np.ascontiguousarray(np.asarray(X[hdf5_idx], dtype=np.float32).T)
            in_path = os.path.join(sup_dir, f"input_{out_idx:03d}.bin")
            planar.tofile(in_path)
            m23 = merged32[p].astype(np.float32)
            argmax23 = int(pred23[p])
            prob = softmax(m23)
            tsv_lines.append(
                f"{out_idx}\t{argmax23}\t{src_class}\t"
                f"{DEPLOYED_LABEL_ORDER_23[argmax23]}\t{prob[argmax23]:.6f}\n")
            samples.append({
                "index": out_idx, "subset_position": p, "hdf5_index": hdf5_idx,
                "source_class": src_class,
                "source_label": SOURCE_LABEL_ORDER_24[src_class],
                "snr_db": float(sub_snrs[p]),
                "input_file": f"input_{out_idx:03d}.bin",
                "merged23_argmax": argmax23,
                "argmax_class_23": DEPLOYED_LABEL_ORDER_23[argmax23],
            })

    with open(os.path.join(sup_dir, "expected_argmax.tsv"), "w", encoding="utf-8", newline="\n") as fh:
        fh.writelines(tsv_lines)
    manifest = {
        "purpose": "coverage audit ONLY -- the board gate NEVER reads this directory",
        "strategy": "for each deployed class missing from the main 240 expected "
                    "argmax, add up to 5 remaining frames (by ascending sub_indices) "
                    "whose expected argmax is that class; deterministic, reproducible.",
        "num_samples": len(rows),
        "missing_deployed_classes": missing,
        "per_missing_class_cap": k_per_missing,
        "samples": samples,
    }
    with open(os.path.join(sup_dir, "manifest.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"  coverage_supplemental/: {len(rows)} frames covering missing classes {missing}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Regenerate the RML23 conformance golden.")
    ap.add_argument("--out", default=os.path.join(_BOARD_LIVE, "deployment_golden"))
    ap.add_argument("--model-json",
                    default=os.path.join(_BOARD_LIVE, "model_rml23", "model_24class_ZG.json"))
    ap.add_argument("--model-raw",
                    default=os.path.join(_BOARD_LIVE, "model_rml23", "model_24class_ZG.raw"))
    ap.add_argument("--expA-logits",
                    default=r"F:/FPGA_Work/_tmp_24class_expA_bf16_head_384_20261010_eval_result/expA_logits.npy")
    ap.add_argument("--subset",
                    default=os.path.join(_M29, "work", "eval_full", "subset_index.npz"))
    ap.add_argument("--hdf5",
                    default=r"F:/datasets/RadioML2018/GOLD_XYZ_OSC.0001_1024.hdf5")
    ap.add_argument("--ref-dir",
                    default=os.path.join(_M29, "board_rml23", "test_data"))
    args = ap.parse_args()

    for p in (args.model_json, args.model_raw, args.expA_logits, args.subset, args.hdf5):
        if not os.path.exists(p):
            fail(f"missing input path: {p}")

    verify_identity(args)
    logits24, merged32, pred23, sub_indices, sub_labels, sub_snrs = \
        load_and_assert_reference(args)
    selected = select_main_set(sub_indices, sub_labels)
    write_golden(args, selected, logits24, merged32, pred23,
                 sub_indices, sub_labels, sub_snrs)
    print("== gen_rml23_golden: PASS ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
