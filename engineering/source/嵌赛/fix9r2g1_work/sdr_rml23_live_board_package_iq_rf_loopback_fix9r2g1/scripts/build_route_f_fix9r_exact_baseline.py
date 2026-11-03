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
(source_index / original_sha256 / deployed_class / split_role), the modulation
name, plus the FROZEN offline model prediction `frozen_baseline_pred` (fix9r2g).

`frozen_baseline_pred` is NOT `deployed_class` (the ground-truth label): it is the
model's prediction computed OFFLINE (on AutoDL) and supplied here via
`--predictions`, so the R8 board run can compare the RF-recovered model prediction
against a pre-frozen offline prediction without re-running the model on the API
machine.  Falling back to `deployed_class` would collapse "prediction agreement"
into "classification correctness" and is forbidden.

Pure stdlib (no numpy).  Fail-closed: it raises on a malformed row, a non-64-hex
sha, an out-of-range deployed class, a holdout count != the expected count, a
missing/duplicate/out-of-range frozen prediction, or a prediction set that does not
exactly cover the holdout source_index set.

Usage (on the board, after the D2 artifact build and offline prediction pass):
    python3 -I scripts/build_route_f_fix9r_exact_baseline.py \
        --d2-manifest /root/rml23_route_d2_rf_fix9/route_d2_rf_manifest.tsv \
        --predictions /root/rml23_route_f_fix9r_predictions.tsv \
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
                   "modulation", "split_role", "frozen_baseline_pred"]

# Offline-prediction TSV: one row per scored sample, keyed by source_index.
PRED_HEADER = ["source_index", "file_name", "frozen_baseline_pred"]


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


def parse_predictions(path: str, class_count: int = 23) -> dict:
    """Parse the offline-prediction TSV -> {source_index: frozen_baseline_pred}.

    Fail-closed: empty file, bad header, short row, duplicate source_index, or an
    out-of-range prediction all raise.  `frozen_baseline_pred` must be in
    [0, class_count); it is the model's own prediction, NOT the ground-truth label.
    """
    pred = {}
    with open(path, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    if not lines:
        raise ValueError("empty predictions %s" % path)
    header = lines[0].split("\t")
    if len(header) < 3 or header[0] != "source_index" or header[2] != "frozen_baseline_pred":
        raise ValueError("predictions %s has no 3-column header" % path)
    for line in lines[1:]:
        if not line:
            continue
        p = line.split("\t")
        if len(p) < 3:
            raise ValueError("bad predictions row (want 3 cols): %r" % line)
        source_index = int(p[0])
        frozen = int(p[2])
        if not p[1]:
            raise ValueError("empty file_name for source_index %d" % source_index)
        if frozen < 0 or frozen >= class_count:
            raise ValueError("frozen_baseline_pred out of range %d for source_index %d"
                             % (frozen, source_index))
        if source_index in pred:
            raise ValueError("duplicate predictions source_index %d" % source_index)
        pred[source_index] = frozen
    if not pred:
        raise ValueError("predictions is empty: %s" % path)
    return pred


def attach_predictions(holdout: list, pred: dict) -> list:
    """Attach frozen_baseline_pred to each holdout row by exact source_index key.

    Fail-closed: the prediction key set must EXACTLY cover the holdout source_index
    set (a missing or extra source_index raises).  No row-number / fuzzy-name match.
    """
    holdout_keys = {r["source_index"] for r in holdout}
    if len(holdout_keys) != len(holdout):
        raise ValueError("duplicate source_index within holdout rows")
    if holdout_keys != set(pred):
        missing = sorted(holdout_keys - set(pred))
        extra = sorted(set(pred) - holdout_keys)
        raise ValueError("prediction keys != holdout keys: missing=%s extra=%s"
                         % (missing, extra))
    for r in holdout:
        r["frozen_baseline_pred"] = pred[r["source_index"]]
    return holdout


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
    ap.add_argument("--predictions", default=None)
    ap.add_argument("--out", default="route_f_fix9r_exact_baseline.tsv")
    ap.add_argument("--expect-holdout", type=int, default=46)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()
    if not args.d2_manifest:
        ap.error("--d2-manifest is required (or use --self-test)")
    if not args.predictions:
        ap.error("--predictions is required: the API cannot run the model offline")

    rows = parse_d2_manifest(args.d2_manifest)
    holdout = derive_baseline(rows, args.expect_holdout)
    pred = parse_predictions(args.predictions)
    holdout = attach_predictions(holdout, pred)
    write_baseline(args.out, holdout)

    dist = {}
    for r in holdout:
        dist[r["deployed_class"]] = dist.get(r["deployed_class"], 0) + 1
    print("ROUTE_F_FIX9R_EXACT_BASELINE manifest_rows=%d holdout=%d predictions=%d out=%s"
          % (len(rows), len(holdout), len(pred), args.out))
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

    # 2. predictions attach: exact source_index mapping, frozen != deployed.
    ppath = os.path.join(tmp, "predictions.tsv")
    with open(ppath, "w", encoding="utf-8") as f:
        f.write("\t".join(PRED_HEADER) + "\n")
        for i in range(46):
            frozen = (i * 7 + 3) % 23
            f.write("%d\tq_%06d.ci16\t%d\n" % (1000 + i, i, frozen))
    pred = parse_predictions(ppath)
    attached = attach_predictions(holdout, pred)
    ok = len(attached) == 46 and all(
        r["frozen_baseline_pred"] == (i * 7 + 3) % 23
        for i, r in enumerate(attached))
    # frozen_baseline_pred is a model prediction, deliberately != deployed label.
    ok = ok and any(r["frozen_baseline_pred"] != r["deployed_class"] for r in attached)
    if ok:
        npass += 1
        print("  OK  predictions attached by exact source_index key")
    else:
        print("  BAD predictions attach")

    # 3. write_baseline emits 6-column header + rows.
    out_path = os.path.join(tmp, "base.tsv")
    write_baseline(out_path, attached)
    with open(out_path, "r", encoding="utf-8") as f:
        wl = f.read().splitlines()
    if len(wl) == 47 and wl[0].split("\t") == BASELINE_HEADER and \
            wl[1].split("\t")[5] == str((0 * 7 + 3) % 23):
        npass += 1
        print("  OK  write_baseline 6-column header + rows")
    else:
        print("  BAD write_baseline 6-column")

    # 4. holdout count mismatch -> fail-closed.
    try:
        derive_baseline(rows, 45)
        print("  BAD holdout-count mismatch not detected")
    except ValueError:
        npass += 1
        print("  OK  holdout-count mismatch detected")

    # 5. malformed (23-col) row -> fail-closed.
    mbad = os.path.join(tmp, "bad.tsv")
    with open(mbad, "w", encoding="utf-8") as f:
        f.write(header + "\n" + "\t".join(["0"] * 23) + "\n")
    try:
        parse_d2_manifest(mbad)
        print("  BAD malformed row not detected")
    except ValueError:
        npass += 1
        print("  OK  malformed row detected")

    # 6. bad sha (not 64-hex) -> fail-closed.
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

    # 7. non-holdout/calibration split_role -> fail-closed.
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

    # 8. missing prediction (drop one source_index) -> fail-closed.
    pred_missing = {k: v for k, v in pred.items() if k != 1000}
    try:
        attach_predictions(holdout, pred_missing)
        print("  BAD missing prediction not detected")
    except ValueError:
        npass += 1
        print("  OK  missing prediction detected")

    # 9. extra prediction (add unknown source_index) -> fail-closed.
    pred_extra = dict(pred)
    pred_extra[99999] = 3
    try:
        attach_predictions(holdout, pred_extra)
        print("  BAD extra prediction not detected")
    except ValueError:
        npass += 1
        print("  OK  extra prediction detected")

    # 10. out-of-range frozen_baseline_pred -> fail-closed.
    pbad = os.path.join(tmp, "pred_bad.tsv")
    with open(pbad, "w", encoding="utf-8") as f:
        f.write("\t".join(PRED_HEADER) + "\n")
        for i in range(46):
            f.write("%d\tq_%06d.ci16\t%d\n" % (1000 + i, i, 23 if i == 0 else 0))
    try:
        parse_predictions(pbad)
        print("  BAD out-of-range prediction not detected")
    except ValueError:
        npass += 1
        print("  OK  out-of-range frozen_baseline_pred detected")

    # 11. duplicate prediction source_index -> fail-closed.
    pdup = os.path.join(tmp, "pred_dup.tsv")
    with open(pdup, "w", encoding="utf-8") as f:
        f.write("\t".join(PRED_HEADER) + "\n")
        f.write("1000\tq_000000.ci16\t1\n1000\tq_000001.ci16\t2\n")
    try:
        parse_predictions(pdup)
        print("  BAD duplicate prediction not detected")
    except ValueError:
        npass += 1
        print("  OK  duplicate prediction detected")

    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
    print("self-test: %d/11 correct" % npass)
    return 0 if npass == 11 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
