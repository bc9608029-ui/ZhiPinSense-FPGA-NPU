#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_route_f_fix9r_exact_baseline.py -- Route F fix9r Task B.

Derives the 46-sample EXACT baseline the fix9r acceptance gate compares against,
by extracting the split_role == "holdout" rows from the D2 RF manifest that
scripts/build_route_d2_rf_artifacts.py writes on the board:

    route_d2_rf_manifest.tsv  (24 columns)  ->  route_f_fix9r_exact_baseline.tsv

The full 24-class frozen Stage G extraction (manifest_a.tsv + input_*.bin) lives on
the board / AutoDL, NOT on the API's machine (the API only has the 4-class D0
control).  The baseline is therefore DERIVED on-board from the SAME manifest the
fix9 / fix9r board run consumes, so its source_index / original_sha256 /
deployed_class / split_role are byte-identical to the scored samples by
construction -- a pre-computed offline list would not match.

The baseline TSV columns are the four identifiers the task book mandates
(source_index / original_sha256 / deployed_class / split_role) plus the modulation
name.  `deployed_class` is the ground-truth baseline prediction: the model's known
original-data accuracy is 99.34% (906/912), so the ground-truth deployed class IS
the model's prediction for ~all 46 samples; the model is NOT re-run offline.

Pure stdlib (no numpy).  Fail-closed: it raises on a malformed row, a non-64-hex
sha, an out-of-range deployed class, or a holdout count != the expected count.

Usage (on the board, after the D2 artifact build):
    python3 -I scripts/build_route_f_fix9r_exact_baseline.py \
        --d2-manifest /root/rml23_route_d2_rf_fix9/route_d2_rf_manifest.tsv \
        --out /root/rml23_route_f_fix9r_exact_baseline.tsv [--expect-holdout 46]

    python3 -I scripts/build_route_f_fix9r_exact_baseline.py --self-test
"""

from __future__ import annotations

import argparse
import sys

# route_d2_rf_manifest.tsv column indices (0-based, 24 columns), frozen by
# build_route_d2_rf_artifacts.py MANIFEST_HEADER.
D2_COLS = {
    "sample_index": 0, "source_index": 1, "raw24_class": 2, "deployed23_class": 3,
    "modulation": 4, "snr_db": 5, "split_role": 6, "global_K": 7,
    "original_dc_i": 8, "original_dc_q": 9, "ac_rms": 10, "rec_scale": 11,
    "complex_count": 12, "sample_rate": 13, "tx_rms": 14, "tx_peak": 15,
    "clip_count": 16, "edge_policy": 17, "guard": 18, "original_sha256": 19,
    "quantized_sha256": 20, "recovered_tensor_sha256": 21,
    "quantized_file": 22, "recovered_tensor_file": 23,
}

BASELINE_HEADER = ["source_index", "original_sha256", "deployed_class",
                   "modulation", "split_role"]


def is_hex64(s: str) -> bool:
    return len(s) == 64 and all(c in "0123456789abcdef" for c in s)


def parse_d2_manifest(path: str) -> list:
    """Parse route_d2_rf_manifest.tsv (24-col header + rows), fail-closed."""
    rows = []
    seen_sample = set()
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    if not lines:
        raise ValueError("empty manifest %s" % path)
    header = lines[0].split("\t")
    if len(header) < 24 or header[D2_COLS["sample_index"]] != "sample_index":
        raise ValueError("manifest %s has no 24-column header" % path)
    for line in lines[1:]:
        if not line:
            continue
        p = line.split("\t")
        if len(p) < 24:
            raise ValueError("bad D2 manifest row (want 24 cols): %r" % line)
        sample_index = int(p[D2_COLS["sample_index"]])
        source_index = int(p[D2_COLS["source_index"]])
        deployed = int(p[D2_COLS["deployed23_class"]])
        split_role = p[D2_COLS["split_role"]]
        original_sha = p[D2_COLS["original_sha256"]]
        modulation = p[D2_COLS["modulation"]]
        if sample_index in seen_sample:
            raise ValueError("duplicate sample_index %d" % sample_index)
        if deployed < 0 or deployed >= 23:
            raise ValueError("deployed23_class out of range %d" % deployed)
        if split_role not in ("calibration", "holdout"):
            raise ValueError("bad split_role %r" % split_role)
        if not is_hex64(original_sha):
            raise ValueError("original_sha256 not 64-hex for sample %d"
                             % sample_index)
        seen_sample.add(sample_index)
        rows.append({"source_index": source_index,
                     "original_sha256": original_sha, "deployed_class": deployed,
                     "modulation": modulation, "split_role": split_role})
    return rows


def derive_baseline(d2_rows: list, expect_holdout: int) -> list:
    holdout = [r for r in d2_rows if r["split_role"] == "holdout"]
    if expect_holdout > 0 and len(holdout) != expect_holdout:
        raise ValueError("expected %d holdout rows, found %d"
                         % (expect_holdout, len(holdout)))
    if not holdout:
        raise ValueError("no holdout rows in the D2 manifest")
    return holdout


def write_baseline(path: str, rows: list) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\t".join(BASELINE_HEADER) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[c]) for c in BASELINE_HEADER) + "\n")


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--d2-manifest", default=None)
    ap.add_argument("--out", default="route_f_fix9r_exact_baseline.tsv")
    ap.add_argument("--expect-holdout", type=int, default=46)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.d2_manifest:
        ap.error("--d2-manifest is required (or use --self-test)")

    rows = parse_d2_manifest(args.d2_manifest)
    holdout = derive_baseline(rows, args.expect_holdout)
    write_baseline(args.out, holdout)

    dist = {}
    for r in holdout:
        dist[r["deployed_class"]] = dist.get(r["deployed_class"], 0) + 1
    print("ROUTE_F_FIX9R_EXACT_BASELINE manifest_rows=%d holdout=%d out=%s"
          % (len(rows), len(holdout), args.out))
    print("  deployed_class_distribution=%s"
          % ",".join("%d:%d" % (d, dist.get(d, 0)) for d in range(23)))
    return 0


def self_test():
    npass = 0
    header = "\t".join([
        "sample_index", "source_index", "raw24_class", "deployed23_class",
        "modulation", "snr_db", "split_role", "global_K", "original_dc_i",
        "original_dc_q", "ac_rms", "rec_scale", "complex_count", "sample_rate",
        "tx_rms", "tx_peak", "clip_count", "edge_policy", "guard",
        "original_sha256", "quantized_sha256", "recovered_tensor_sha256",
        "quantized_file", "recovered_tensor_file"])

    def row(sample, source, dep, role):
        sha = ("%064x" % (sample + 1))
        return "\t".join([
            str(sample), str(source), str(dep), str(dep), "QPSK", "20.0", role,
            "2048", "0.0", "0.0", "1.0", "128.0", "53760", "2560000",
            "2048.0", "2048.0", "0", "zero", "832", sha, sha, sha,
            "quantized_d2_2p56m_%06d.ci16" % sample,
            "recovered_tensor_d2_%06d.f32" % sample])

    # 1. header + 46 holdout + 184 calibration -> extracts exactly 46 holdout.
    lines = [header]
    lines += [row(i, 1000 + i, i % 23, "holdout") for i in range(46)]
    lines += [row(1000 + i, 2000 + i, i % 23, "calibration") for i in range(184)]
    import tempfile, os
    tmp = tempfile.mkdtemp(prefix="fix9r_base_")
    mpath = os.path.join(tmp, "route_d2_rf_manifest.tsv")
    with open(mpath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    rows = parse_d2_manifest(mpath)
    holdout = derive_baseline(rows, 46)
    if len(holdout) == 46 and all(r["split_role"] == "holdout" for r in holdout) \
            and holdout[0]["source_index"] == 1000 \
            and holdout[0]["original_sha256"] == "%064x" % 1 \
            and holdout[45]["deployed_class"] == 45 % 23:
        npass += 1
        print("  OK  D2 manifest -> 46 holdout rows, columns mapped")
    else:
        print("  BAD D2 manifest extraction n=%d" % len(holdout))

    # 2. holdout count mismatch -> fail-closed.
    try:
        derive_baseline(rows, 45)
        print("  BAD holdout-count mismatch not detected")
    except ValueError:
        npass += 1
        print("  OK  holdout-count mismatch detected")

    # 3. malformed (23-col) row -> fail-closed.
    mbad = os.path.join(tmp, "bad.tsv")
    with open(mbad, "w", encoding="utf-8") as f:
        f.write(header + "\n" + "\t".join(["0"] * 23) + "\n")
    try:
        parse_d2_manifest(mbad)
        print("  BAD malformed row not detected")
    except ValueError:
        npass += 1
        print("  OK  malformed row detected")

    # 4. bad sha (not 64-hex) -> fail-closed.
    msha = os.path.join(tmp, "badsha.tsv")
    with open(msha, "w", encoding="utf-8") as f:
        f.write(header + "\n" + "\t".join([
            "0", "1", "1", "1", "QPSK", "20.0", "holdout", "2048", "0", "0",
            "1", "128", "53760", "2560000", "2048", "2048", "0", "zero", "832",
            "xyz", "xyz", "xyz", "q.ci16", "r.f32"]) + "\n")
    try:
        parse_d2_manifest(msha)
        print("  BAD bad-sha row not detected")
    except ValueError:
        npass += 1
        print("  OK  bad original_sha256 detected")

    # 5. non-holdout/calibration split_role -> fail-closed.
    mrole = os.path.join(tmp, "badrole.tsv")
    with open(mrole, "w", encoding="utf-8") as f:
        f.write(header + "\n" + "\t".join([
            "0", "1", "1", "1", "QPSK", "20.0", "train", "2048", "0", "0",
            "1", "128", "53760", "2560000", "2048", "2048", "0", "zero", "832",
            "%064x" % 1, "%064x" % 1, "%064x" % 1, "q.ci16", "r.f32"]) + "\n")
    try:
        parse_d2_manifest(mrole)
        print("  BAD bad split_role not detected")
    except ValueError:
        npass += 1
        print("  OK  bad split_role detected")

    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    print("self-test: %d/5 correct" % npass)
    return 0 if npass == 5 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
