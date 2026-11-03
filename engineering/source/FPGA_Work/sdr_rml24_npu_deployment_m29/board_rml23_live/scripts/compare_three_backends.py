#!/usr/bin/env python3
"""compare_three_backends.py -- three-backend raw-24 logits comparator (errata 39e5 Stage E, #7).

Locates the QPSK->QAM classification jump by comparing, for IDENTICAL input bytes,
the raw 24-dim pre-merge logits produced by three independent backends:

    board_npu      iCraft NPU backend, bf16-compiled model_24class_ZG (ZG330)
    host_quantized iCraft HostBackend, the SAME bf16 model run on CPU (frozen export)
    fp32_onnx      the FP32 source model work/onnx/rml24_24class_opset17.onnx

Comparison is keyed by input SHA-256: a backend's export is only ever compared
against another export that came from the SAME 8192 input bytes, and every export
must declare the same compiled-model identity (model_raw_sha256 ==
2425d990...).  A wrong-identity or wrong-input record is REJECTED, never silently
compared.

Outputs, for every pair of present backends and every matched frame:
    max_abs_diff (raw24), cosine (raw24), and merged-23 argmax agreement.
The 24->23 merge uses the frozen postprocess/rml23_merged.py logaddexp rule.

This tool NEVER fabricates a backend and NEVER claims a three-backend verdict when
a backend is missing.  When a backend is unavailable it prints UNAVAILABLE plus
the exact pending command to produce that export.

Usage:
    python scripts/compare_three_backends.py --inventory
    python scripts/compare_three_backends.py \
        --fp32-dir /tmp/fp32 \
        [--board-dir /tmp/board_logits]          # omit = UNAVAILABLE (board only)
        [--host-json deployment_golden/expected_logits_or_argmax.json]

stdlib + numpy (+ onnxruntime only for --inventory probing).
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import json
import math
import os
import sys

import numpy as np

FROZEN_MODEL_RAW_SHA256 = "2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba"

_HERE = os.path.dirname(os.path.abspath(__file__))


def load_merge_module(merge_module_path=None):
    """Load the frozen postprocess/rml23_merged.py (errata 39e5 import fix).

    The independent board package does NOT ship postprocess/rml23_merged.py, so
    the previous ``sys.path.insert(_HERE/../../postprocess)`` import failed when
    the package was unpacked standalone.  We resolve the FROZEN merge module in
    order -- explicit ``--merge-module``, a package-local copy, then the frozen
    project layout (board_rml23_live/scripts -> ../../postprocess) -- and load it
    by file path.  Loading by file path keeps ``rml23_merged.py``'s own
    ``../contracts`` import resolving against its real location, so the official
    merge and contract are reused verbatim (never reimplemented).
    """
    candidates = []
    if merge_module_path:
        candidates.append(os.path.abspath(merge_module_path))
    for rel in ("../postprocess/rml23_merged.py",          # package-local copy
                "../../postprocess/rml23_merged.py"):      # frozen project layout
        candidates.append(os.path.abspath(os.path.join(_HERE, rel)))
    seen = set()
    for c in candidates:
        if c in seen or not os.path.isfile(c):
            continue
        seen.add(c)
        import importlib.util
        spec = importlib.util.spec_from_file_location("rml23_merged", c)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    raise ImportError(
        "postprocess/rml23_merged.py not found; pass --merge-module PATH to the "
        "frozen project's postprocess/rml23_merged.py (candidates tried: %s)"
        % ", ".join(seen))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_dir_export(exp_dir, backend_tag):
    """Load {input_sha256: {"raw24": [...], "model_sha": str, "frame_id": int}}
    from a directory of logits_*.json, rejecting wrong-backend records."""
    recs = {}
    for path in sorted(glob.glob(os.path.join(exp_dir, "logits_*.json"))):
        with open(path, "r", encoding="utf-8") as f:
            r = json.load(f)
        if r.get("backend") != backend_tag:
            raise ValueError(
                "%s declares backend %r, expected %r" % (path, r.get("backend"), backend_tag))
        recs[r["input_sha256"]] = r
    return recs


def load_host_export(host_json, golden_dir):
    """Load the frozen HostBackend export from the golden provenance JSON, keyed
    by the SHA-256 of each input_NNN.bin."""
    with open(host_json, "r", encoding="utf-8") as f:
        doc = json.load(f)
    if doc.get("model_raw_sha256") != FROZEN_MODEL_RAW_SHA256:
        raise ValueError("host provenance model_raw_sha256 != frozen identity")
    recs = {}
    for s in doc["samples"]:
        inp = os.path.join(golden_dir, s["input_file"])
        sha = sha256_file(inp)
        recs[sha] = {
            "backend": "host_quantized",
            "frame_id": s["index"],
            "input_sha256": sha,
            "model_sha": FROZEN_MODEL_RAW_SHA256,
            "raw24": s["raw_24_logits"],
        }
    return recs


def check_identity(rec, backend_tag):
    """Fail closed unless a backend's record declares the frozen compiled model."""
    if backend_tag == "fp32_onnx":
        if rec.get("compiled_model_raw_sha256") != FROZEN_MODEL_RAW_SHA256:
            raise ValueError("fp32 export compiled_model_raw_sha256 != frozen identity")
        return  # the fp32 onnx model_sha is its own file sha (recorded, not frozen)
    if rec.get("model_sha") != FROZEN_MODEL_RAW_SHA256:
        raise ValueError(
            "%s export model_sha %r != frozen %s"
            % (backend_tag, rec.get("model_sha"), FROZEN_MODEL_RAW_SHA256))


def argmax_merged(raw24, merge_mod):
    m23 = merge_mod.merge_logits_24_to_23([float(v) for v in raw24])
    return int(max(range(len(m23)), key=lambda k: m23[k]))


def pair_stats(a, b):
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    d = np.abs(a - b)
    cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-300))
    return float(d.max()), cos


def inventory():
    """Probe the LOCAL environment for the three backends and report honestly."""
    print("three-backend inventory (this host):")
    print()

    # fp32 onnx
    onnx_ok = False
    try:
        import onnxruntime  # noqa: F401
        onnx_ok = True
    except ImportError:
        onnx_ok = False
    onnx_path = os.path.abspath(os.path.join(_HERE, os.pardir, os.pardir,
                                             "work", "onnx", "rml24_24class_opset17.onnx"))
    if onnx_ok and os.path.isfile(onnx_path):
        print("  fp32_onnx       AVAILABLE   (onnxruntime + %s)" % onnx_path)
        print("                   export: python scripts/export_fp32_onnx.py "
              "--input-dir deployment_golden --out-dir /tmp/fp32")
    else:
        print("  fp32_onnx       UNAVAILABLE")
        if not onnx_ok:
            print("                   pending: pip install onnxruntime")
        else:
            print("                   pending: ONNX not found at %s" % onnx_path)

    # host quantized
    host_json = os.path.join(_HERE, "..", "deployment_golden",
                             "expected_logits_or_argmax.json")
    host_json = os.path.abspath(host_json)
    if os.path.isfile(host_json):
        print("  host_quantized  AVAILABLE   (frozen HostBackend export, 240 frames)")
        print("                   %s" % host_json)
        print("                   (iCraft HostBackend RUNTIME is not installed here; "
              "the frozen result is used)")
    else:
        print("  host_quantized  UNAVAILABLE  pending: regenerate the conformance golden")

    # board npu
    print("  board_npu       UNAVAILABLE (no ZG330 / iCraft NPU backend on this host)")
    print("                   pending (on the FMQL30TAI board):")
    print("                     bash scripts/run_gate9_rml23.sh --phase=offline "
          "--count=240 --logits-export=/tmp/board_logits")
    print()
    print("verdict: a full three-backend judgment requires the board_npu export; "
          "only fp32-vs-host (quantization) is runnable here.")
    return 0


def compare(args):
    present = {}
    missing = {}

    merge_mod = load_merge_module(args.merge_module)

    # fp32
    if args.fp32_dir:
        fp = load_dir_export(args.fp32_dir, "fp32_onnx")
        for r in fp.values():
            check_identity(r, "fp32_onnx")
        present["fp32_onnx"] = fp
    else:
        missing["fp32_onnx"] = "python scripts/export_fp32_onnx.py " \
            "--input-dir deployment_golden --out-dir /tmp/fp32"

    # host: prefer a live host_quantized logits_*.json dir (--host-dir), fall back
    # to the frozen golden provenance JSON (--host-json) for the 240 golden frames.
    if args.host_dir:
        hs = load_dir_export(args.host_dir, "host_quantized")
        for r in hs.values():
            check_identity(r, "host_quantized")
        present["host_quantized"] = hs
    else:
        host_json = args.host_json
        if not host_json:
            host_json = os.path.abspath(os.path.join(
                _HERE, "..", "deployment_golden", "expected_logits_or_argmax.json"))
        golden_dir = os.path.dirname(host_json)
        if os.path.isfile(host_json):
            present["host_quantized"] = load_host_export(host_json, golden_dir)
        else:
            missing["host_quantized"] = "regenerate the conformance golden (%s)" % host_json

    # board
    if args.board_dir:
        bd = load_dir_export(args.board_dir, "board_npu")
        for r in bd.values():
            check_identity(r, "board_npu")
        present["board_npu"] = bd
    else:
        missing["board_npu"] = "bash scripts/run_gate9_rml23.sh --phase=offline " \
            "--count=240 --logits-export=/tmp/board_logits"

    print("backends present: %s" % (", ".join(sorted(present)) or "(none)"))
    for tag, cmd in sorted(missing.items()):
        print("  UNAVAILABLE %-15s pending: %s" % (tag, cmd))
    print()

    pairs = [("fp32_onnx", "host_quantized"), ("board_npu", "host_quantized"),
             ("board_npu", "fp32_onnx")]
    any_compared = False
    # per-frame rows keyed by input sha, so the three backends align on identical bytes
    rows = {}
    for tag_a, tag_b in pairs:
        if tag_a not in present or tag_b not in present:
            continue
        a, b = present[tag_a], present[tag_b]
        common = sorted(set(a) & set(b))
        if not common:
            print("%s vs %s: no shared input SHA (cannot compare)" % (tag_a, tag_b))
            continue
        any_compared = True
        diffs, coss, arg_agree = [], [], 0
        for sha in common:
            ra, rb = a[sha]["raw24"], b[sha]["raw24"]
            d, c = pair_stats(ra, rb)
            diffs.append(d)
            coss.append(c)
            if argmax_merged(ra, merge_mod) == argmax_merged(rb, merge_mod):
                arg_agree += 1
            row = rows.setdefault(sha, {"inputs": set(), "top1": {}})
            row["inputs"].add(tag_a)
            row["inputs"].add(tag_b)
            row["top1"][tag_a] = argmax_merged(ra, merge_mod)
            row["top1"][tag_b] = argmax_merged(rb, merge_mod)
        diffs = np.array(diffs)
        print("%s vs %s: %d shared frames" % (tag_a, tag_b, len(common)))
        print("  raw24 max_abs_diff  min=%.6g median=%.6g max=%.6g"
              % (diffs.min(), float(np.median(diffs)), diffs.max()))
        print("  raw24 cosine        min=%.6f median=%.6f max=%.6f"
              % (min(coss), float(np.median(coss)), max(coss)))
        print("  merged-23 argmax agree  %d/%d" % (arg_agree, len(common)))
        print()

    if not any_compared:
        print("NO PAIR COMPARED: every comparison needs at least two backends.  "
              "No three-backend verdict is claimed.")
        return 2

    # ---- per-frame top-1 trajectory + confusion histogram (all aligned rows) ----
    from collections import Counter
    print("per-frame top-1 (board_npu / host_quantized / fp32_onnx):")
    n_three = 0
    agree_all = 0
    for sha in sorted(rows):
        t = rows[sha]["top1"]
        b = t.get("board_npu")
        h = t.get("host_quantized")
        f = t.get("fp32_onnx")
        print("  %s  npu=%s host=%s fp32=%s" % (
            sha[:16],
            b if b is not None else "-",
            h if h is not None else "-",
            f if f is not None else "-"))
        if b is not None and h is not None and f is not None:
            n_three += 1
            if b == h == f:
                agree_all += 1
    if n_three:
        print("all three backends share a frame on %d inputs; top-1 all-agree %d/%d"
              % (n_three, agree_all, n_three))
    for tag in ("board_npu", "host_quantized", "fp32_onnx"):
        if tag not in present:
            continue
        hist = Counter(rows[sha]["top1"][tag] for sha in rows if tag in rows[sha]["top1"])
        print("  %-14s merged-23 argmax histogram: %s" % (tag, dict(sorted(hist.items()))))

    if "board_npu" in missing:
        print("board_npu is UNAVAILABLE: the above is a %d-backend comparison, NOT "
              "a three-backend judgment.  Produce the board export and re-run to "
              "complete the third backend." % len(present))
    else:
        print("all three backends present: comparison is a full three-backend judgment.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--inventory", action="store_true",
                    help="probe local backend availability and print pending commands")
    ap.add_argument("--board-dir", default=None,
                    help="dir of board_npu logits_*.json (from --logits-export on board)")
    ap.add_argument("--fp32-dir", default=None,
                    help="dir of fp32_onnx logits_*.json (from export_fp32_onnx.py)")
    ap.add_argument("--host-dir", default=None,
                    help="dir of host_quantized logits_*.json (icraft-run --backends Host)")
    ap.add_argument("--host-json", default=None,
                    help="host provenance JSON (default deployment_golden/expected_logits_or_argmax.json)")
    ap.add_argument("--merge-module", default=None,
                    help="path to the frozen postprocess/rml23_merged.py (default auto-detect)")
    args = ap.parse_args()

    if args.inventory:
        return inventory()
    return compare(args)


if __name__ == "__main__":
    sys.exit(main())
