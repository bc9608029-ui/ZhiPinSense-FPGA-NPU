#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_rml24_prewarm_plan.py -- deterministic 24-sample PC-side prewarm plan.

fix10class24-dualsdr1 §14 (Phase C): before the board runs the REAL 24-class dual-SDR
loop, the PC owns the TX SDR and must prewarm (build the canonical TX burst for) all
24 holdout samples ahead of time -- the PREPARE window must never launch WSL/g++, so
every burst is built in prewarm and PREPARE only reads the cache.  This script is the
single source of truth for WHICH 24 samples to prewarm and the per-sample identity the
prewarm + PREPARE both check against.

It reads the frozen 24-column D2 manifest (clean24_smoke/route_d2_rf_manifest.tsv),
fail-closed on the exact 24-sample holdout set, re-hashes every quantized CI16 on disk
(byte identity vs the manifest's quantized_sha256), and emits two artifacts:

    <out-dir>/rml24_prewarm_plan.tsv   source_index  file_name  complex_count
                                       quantized_sha256  target_rms
    <out-dir>/rml24_prewarm_plan.json  per-sample plan + counts + sha cross-check

The plan is DETERMINISTIC: two runs produce byte-identical output.  It is pure stdlib
(no numpy / h5py / iio / icraft), so it runs on the PC radioconda python AND under the
WSL `python3` host tests, and it never touches the board or the SDR.

Usage:
    python3 -I scripts/build_rml24_prewarm_plan.py \
        --frozen-dir clean24_smoke --out-dir results/rml24_prewarm --target-rms 2048
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

PLAN_HEADER = "source_index\tfile_name\tcomplex_count\tquantized_sha256\ttarget_rms"

# The frozen D2 manifest's 24-column schema (col index -> field), verbatim.
MANIFEST_COLUMNS = {
    "source_index": 1,
    "raw24_class": 2,
    "deployed23_class": 3,
    "modulation": 4,
    "split_role": 6,
    "complex_count": 12,
    "sample_rate": 13,
    "original_sha256": 19,
    "quantized_sha256": 20,
    "quantized_file": 22,
}

EXPECT_SAMPLE_RATE = 2560000
EXPECT_SOURCE_INDEX_STEP = 500
EXPECT_SAMPLE_COUNT = 24


def fail(msg: str) -> int:
    print("FAIL: %s" % msg, file=sys.stderr)
    return 1


def is_hex64(s: str) -> bool:
    if len(s) != 64:
        return False
    for c in s:
        if not ("0" <= c <= "9" or "a" <= c <= "f"):
            return False
    return True


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(frozen_dir: str) -> list[dict]:
    """Parse the 24-column D2 manifest, fail-closed.  Returns rows as dicts."""
    tsv_path = os.path.join(frozen_dir, "route_d2_rf_manifest.tsv")
    if not os.path.isfile(tsv_path):
        raise ValueError("missing route_d2_rf_manifest.tsv in " + frozen_dir)

    rows = []
    with open(tsv_path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, start=1):
            line = line.rstrip("\n").rstrip("\r")
            if not line:
                continue
            if line.startswith("#"):
                continue
            if lineno == 1:
                continue  # header row
            cols = line.split("\t")
            if len(cols) < 24:
                raise ValueError(
                    "manifest row %d has %d columns (want >=24)" % (lineno, len(cols)))
            def c(name):
                return cols[MANIFEST_COLUMNS[name]]
            rows.append({
                "source_index": int(c("source_index")),
                "raw24_class": int(c("raw24_class")),
                "deployed23_class": int(c("deployed23_class")),
                "modulation": c("modulation"),
                "split_role": c("split_role"),
                "complex_count": int(c("complex_count")),
                "sample_rate": int(c("sample_rate")),
                "original_sha256": c("original_sha256"),
                "quantized_sha256": c("quantized_sha256"),
                "quantized_file": c("quantized_file"),
            })
    return rows


def validate_manifest(rows: list[dict]) -> None:
    """Fail-closed structural checks: exactly 24 holdout samples, 0..11500 step 500."""
    if len(rows) != EXPECT_SAMPLE_COUNT:
        raise ValueError("expected %d manifest rows, got %d"
                         % (EXPECT_SAMPLE_COUNT, len(rows)))
    for r in rows:
        if r["split_role"] != "holdout":
            raise ValueError("manifest row source_index=%d is not holdout (got %r)"
                             % (r["source_index"], r["split_role"]))
        if r["sample_rate"] != EXPECT_SAMPLE_RATE:
            raise ValueError("manifest row source_index=%d sample_rate %d != %d"
                             % (r["source_index"], r["sample_rate"], EXPECT_SAMPLE_RATE))
        if r["complex_count"] <= 0:
            raise ValueError("manifest row source_index=%d bad complex_count %d"
                             % (r["source_index"], r["complex_count"]))
        if not is_hex64(r["quantized_sha256"]):
            raise ValueError("manifest row source_index=%d quantized_sha256 not 64-hex"
                             % r["source_index"])
        if not is_hex64(r["original_sha256"]):
            raise ValueError("manifest row source_index=%d original_sha256 not 64-hex"
                             % r["source_index"])

    rows_sorted = sorted(rows, key=lambda r: r["source_index"])
    for i, r in enumerate(rows_sorted):
        expect = i * EXPECT_SOURCE_INDEX_STEP
        if r["source_index"] != expect:
            raise ValueError("manifest source_index %d at rank %d (expected %d)"
                             % (r["source_index"], i, expect))
        if r["raw24_class"] != i:
            raise ValueError("manifest raw24_class %d != rank %d for source_index %d"
                             % (r["raw24_class"], i, r["source_index"]))
    if len(set(r["source_index"] for r in rows)) != len(rows):
        raise ValueError("duplicate source_index in manifest")


def verify_ci16_bytes(frozen_dir: str, rows: list[dict]) -> None:
    """Re-hash every quantized CI16 on disk against the manifest (byte identity)."""
    for r in rows:
        path = os.path.join(frozen_dir, r["quantized_file"])
        if not os.path.isfile(path):
            raise ValueError("missing quantized file " + path)
        size = os.path.getsize(path)
        expect = r["complex_count"] * 4  # interleaved int16 I/Q
        if size != expect:
            raise ValueError("%s size %d != complex_count*4=%d"
                             % (r["quantized_file"], size, expect))
        got = sha256_file(path)
        if got != r["quantized_sha256"]:
            raise ValueError("%s sha256 %s != manifest %s"
                             % (r["quantized_file"], got, r["quantized_sha256"]))


def build_plan(frozen_dir: str, target_rms: int) -> tuple[list[dict], dict]:
    rows = load_manifest(frozen_dir)
    validate_manifest(rows)
    verify_ci16_bytes(frozen_dir, rows)

    plan = []
    for r in sorted(rows, key=lambda r: r["source_index"]):
        plan.append({
            "source_index": r["source_index"],
            "file_name": r["quantized_file"],
            "complex_count": r["complex_count"],
            "quantized_sha256": r["quantized_sha256"],
            "target_rms": target_rms,
        })

    summary = {
        "plan": "rml24-prewarm-24",
        "frozen_dir": frozen_dir,
        "target_rms": target_rms,
        "sample_count": len(plan),
        "source_index_min": plan[0]["source_index"],
        "source_index_max": plan[-1]["source_index"],
        "source_index_step": EXPECT_SOURCE_INDEX_STEP,
        "all_holdout": True,
        "ci16_sha_verified": len(plan),
        "samples": plan,
    }
    return plan, summary


def render_plan_tsv(plan: list[dict]) -> str:
    lines = [PLAN_HEADER]
    for p in plan:
        lines.append("%d\t%s\t%d\t%s\t%d" % (
            p["source_index"], p["file_name"], p["complex_count"],
            p["quantized_sha256"], p["target_rms"]))
    return "\n".join(lines) + "\n"


def main(argv) -> int:
    ap = argparse.ArgumentParser(description="deterministic 24-sample prewarm plan")
    ap.add_argument("--frozen-dir", default="clean24_smoke")
    ap.add_argument("--out-dir", default="results/rml24_prewarm")
    ap.add_argument("--target-rms", type=int, default=2048)
    args = ap.parse_args(argv)

    try:
        plan, summary = build_plan(args.frozen_dir, args.target_rms)
    except (ValueError, OSError) as e:
        return fail(str(e))

    os.makedirs(args.out_dir, exist_ok=True)
    tsv_path = os.path.join(args.out_dir, "rml24_prewarm_plan.tsv")
    json_path = os.path.join(args.out_dir, "rml24_prewarm_plan.json")
    with open(tsv_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(render_plan_tsv(plan))
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print("RML24_PREWARM_PLAN samples=%d target_rms=%d frozen_dir=%s" %
          (len(plan), args.target_rms, args.frozen_dir))
    print("RML24_PREWARM_PLAN wrote=%s and %s" % (tsv_path, json_path))
    print("RML24_PREWARM_PLAN source_index=%d..%d step=%d all_holdout=1 ci16_sha_verified=%d"
          % (plan[0]["source_index"], plan[-1]["source_index"],
             EXPECT_SOURCE_INDEX_STEP, len(plan)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
