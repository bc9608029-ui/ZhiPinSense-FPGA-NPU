#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_radioml_npu_ab.py -- host-side fail-closed judger for task
fix10class24-original-radioml-npu-ab1: compare the board NPU's 480-frame run
against the frozen Host BF16 reference, frame by frame.

Board outputs (written by board_package/radioml_npu_ab_runner.hpp into --out-dir):
    radioml_npu_ab_results.tsv   (16 columns)
    radioml_npu_ab_logits.tsv    (29 columns)
    radioml_npu_ab_summary.json
    run.log

Host references (read-only, from fix10class24_original_radioml_accuracy1_work):
    frozen_test_selection.tsv
    host_inference/per_sample_results.tsv   (17 columns; host_pred = pred_pass1)
    host_inference/raw24_logits.tsv         (29 columns)

Verdict (independent recompute from the per-sample TSV, never trusting any
GATE_RESULT line):
    MEASUREMENT_COMPLETE_HOST_MATCH        rc=0  all 480 finite + deterministic
                                                  + npu argmax == host argmax
    MEASUREMENT_COMPLETE_HOST_DISAGREEMENT rc=0  all 480 finite + deterministic,
                                                  but some argmax differ
    MEASUREMENT_INCOMPLETE                 rc=1  missing/dup rows, NaN/Inf,
                                                  non-deterministic, header/col
                                                  mismatch, or host-reference
                                                  disagreement on host_pred

This is a MEASUREMENT.  It never prints RF_PASS / PROJECT_COMPLETE / any accuracy
PASS threshold; it only reports agreement and per-SNR/per-class accuracy.
"""
import argparse
import json
import math
import os
import sys

N_FRAMES = 480
N_CLASSES = 24
SNR_LEVELS = (0, 10, 20, 30)

# Frozen 24-class label order (rml24::kLabelOrder24), index -> modulation name.
LABEL_ORDER = [
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
    "FM", "GMSK", "OQPSK",
]

RESULTS_HEADER = ["selection_id", "hdf5_row_index", "raw24_class", "modulation",
                  "snr_db", "finite", "npu_pred_pass1", "npu_pred_pass2",
                  "repeat_deterministic", "label_correct", "host_pred",
                  "npu_host_agree", "top1_logit", "top2_logit", "margin",
                  "result_layer"]

LOGITS_HEADER = ["selection_id", "hdf5_row_index", "raw24_class"] + \
    ["logit_%02d" % c for c in range(N_CLASSES)] + ["pred_pass1", "pred_pass2"]

PER_SAMPLE_HEADER = ["selection_id", "hdf5_row_index", "snr_db", "raw24_class",
                     "modulation", "split", "pred_pass1", "pred_pass2",
                     "label_correct", "finite", "repeat_argmax",
                     "repeat_logits_byte", "top1_logit", "top2_logit", "margin",
                     "model_input_sha256", "result_layer"]

SELECTION_HEADER = ["selection_id", "hdf5_row_index", "snr_db", "raw24_class",
                    "modulation", "split"]

DEFAULT_HOST_RESULTS = "F:/嵌赛/fix10class24_original_radioml_accuracy1_work/results"

# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def fail(msg, rc=1):
    print("AUDIT_RADIOML_NPU_AB FAIL: " + msg, file=sys.stderr)
    sys.exit(rc)


def read_tsv(path, expect_header, n_cols, label):
    with open(path, "r", encoding="utf-8", newline="") as f:
        lines = [ln.rstrip("\r\n") for ln in f]
    if not lines:
        fail("%s: empty file %s" % (label, path))
    header = lines[0].split("\t")
    if header != expect_header:
        fail("%s: header mismatch in %s: got %r" % (label, path, header))
    rows = []
    for i, ln in enumerate(lines[1:], start=2):
        if not ln.strip():
            continue
        cols = ln.split("\t")
        if len(cols) != n_cols:
            fail("%s: line %d has %d columns (want %d) in %s: %r"
                 % (label, i, len(cols), n_cols, path, ln))
        rows.append(cols)
    return rows


def is_finite(s):
    try:
        return math.isfinite(float(s))
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# self-test fixtures (synthetic board + host data)
# ---------------------------------------------------------------------------


def _synth_host_row(sid, hri, cls, mod, snr, pred, top1, top2, margin):
    return [str(sid), str(hri), str(snr), str(cls), mod, "test",
            str(pred), str(pred), "1", "1", "1", "1",
            "%.6f" % top1, "%.6f" % top2, "%.6f" % margin,
            "f" * 64, "HOST_BF16"]


def _synth_board_row(sid, hri, cls, mod, snr, npu_pred, host_pred, finite=1, det=1):
    return [str(sid), str(hri), str(cls), mod, str(snr), str(finite),
            str(npu_pred), str(npu_pred), str(det),
            "1" if npu_pred == cls else "0", str(host_pred),
            "1" if npu_pred == host_pred else "0",
            "%.6f" % (3.0 if npu_pred == 0 else 2.0), "1.0", "2.0", "NPU_BF16"]


def _synth_logits_row(sid, hri, cls, pred):
    logits = ["0.0"] * N_CLASSES
    logits[pred] = "3.0"
    logits[(pred + 1) % N_CLASSES] = "1.0"
    return [str(sid), str(hri), str(cls)] + logits + [str(pred), str(pred)]


def _write_synth(out_dir, board_rows, board_logits, host_rows, host_logits):
    os.makedirs(out_dir, exist_ok=True)

    def w(name, header, rows):
        with open(os.path.join(out_dir, name), "w", encoding="utf-8",
                  newline="") as f:
            f.write("\t".join(header) + "\n")
            for r in rows:
                f.write("\t".join(r) + "\n")

    w("radioml_npu_ab_results.tsv", RESULTS_HEADER, board_rows)
    w("radioml_npu_ab_logits.tsv", LOGITS_HEADER, board_logits)
    os.makedirs(os.path.join(out_dir, "host_inference"), exist_ok=True)
    w(os.path.join("host_inference", "per_sample_results.tsv"),
      PER_SAMPLE_HEADER, host_rows)
    w(os.path.join("host_inference", "raw24_logits.tsv"),
      LOGITS_HEADER, host_logits)
    # frozen_test_selection.tsv + frozen sidecar (identity check only)
    sel_rows = [[str(sid), str(hri), str(snr), str(cls), mod, "test"]
                for (sid, hri, cls, mod, snr) in _sel_fixture()]
    with open(os.path.join(out_dir, "frozen_test_selection.tsv"), "w",
              encoding="utf-8", newline="") as f:
        f.write("\t".join(SELECTION_HEADER) + "\n")
        for r in sel_rows:
            f.write("\t".join(r) + "\n")


def _sel_fixture():
    # 24 classes x {0,10,20,30} x 5 = 480; class 0..23 -> 20 each, snr 120 each.
    out = []
    sid = 1
    for cls in range(N_CLASSES):
        for snr in SNR_LEVELS:
            for k in range(5):
                hri = cls * 4000 + snr * 100 + k
                out.append((sid, hri, cls, LABEL_ORDER[cls], snr))
                sid += 1
    return out


def self_test():
    sel = _sel_fixture()

    def host_rows(pred_of):
        rows = []
        for (sid, hri, cls, mod, snr) in sel:
            p = pred_of(sid, hri, cls, mod, snr)
            rows.append(_synth_host_row(sid, hri, cls, mod, snr, p,
                                        3.0, 1.0, 2.0))
        return rows

    def host_logits(pred_of):
        return [_synth_logits_row(sid, hri, cls, pred_of(sid, hri, cls, mod, snr))
                for (sid, hri, cls, mod, snr) in sel]

    def board_rows(npu_pred_of):
        # host_pred == true label (the Host is correct in every fixture); the NPU
        # may disagree on the "disagree" fixture.
        return [_synth_board_row(sid, hri, cls, mod, snr,
                                 npu_pred_of(sid, hri, cls, mod, snr), cls)
                for (sid, hri, cls, mod, snr) in sel]

    def board_logits(npu_pred_of):
        return [_synth_logits_row(sid, hri, cls,
                                  npu_pred_of(sid, hri, cls, mod, snr))
                for (sid, hri, cls, mod, snr) in sel]

    import tempfile
    cases = []

    # 1. match: npu == host == true label everywhere.
    d = tempfile.mkdtemp(prefix="npuab_match_")
    _write_synth(d, board_rows(lambda *a: a[2]),
                 board_logits(lambda *a: a[2]),
                 host_rows(lambda *a: a[2]), host_logits(lambda *a: a[2]))
    cases.append(("match", d, "MEASUREMENT_COMPLETE_HOST_MATCH", 0))

    # 2. disagreement: one frame flips (npu != host), still finite+deterministic.
    def npu_disagree(sid, hri, cls, mod, snr):
        if sid == 1:
            return (cls + 1) % N_CLASSES
        return cls
    d = tempfile.mkdtemp(prefix="npuab_disagree_")
    _write_synth(d, board_rows(npu_disagree), board_logits(npu_disagree),
                 host_rows(lambda *a: a[2]), host_logits(lambda *a: a[2]))
    cases.append(("disagree", d, "MEASUREMENT_COMPLETE_HOST_DISAGREEMENT", 0))

    # 3. missing row: board has 479 rows.
    d = tempfile.mkdtemp(prefix="npuab_missing_")
    br = board_rows(lambda *a: a[2])
    bl = board_logits(lambda *a: a[2])
    _write_synth(d, br[:-1], bl[:-1],
                 host_rows(lambda *a: a[2]), host_logits(lambda *a: a[2]))
    cases.append(("missing", d, "MEASUREMENT_INCOMPLETE", 1))

    # 4. NaN in logits.
    d = tempfile.mkdtemp(prefix="npuab_nan_")
    bl = board_logits(lambda *a: a[2])
    bl[10][3] = "nan"   # logit_00 of selection_id 11
    _write_synth(d, board_rows(lambda *a: a[2]), bl,
                 host_rows(lambda *a: a[2]), host_logits(lambda *a: a[2]))
    cases.append(("nan", d, "MEASUREMENT_INCOMPLETE", 1))

    # 5. non-deterministic: pass1 != pass2 on one frame.
    d = tempfile.mkdtemp(prefix="npuab_nondet_")
    br = board_rows(lambda *a: a[2])
    br[20][7] = str((int(br[20][7]) + 1) % N_CLASSES)  # npu_pred_pass2
    br[20][8] = "0"                                    # repeat_deterministic
    _write_synth(d, br, board_logits(lambda *a: a[2]),
                 host_rows(lambda *a: a[2]), host_logits(lambda *a: a[2]))
    cases.append(("nondet", d, "MEASUREMENT_INCOMPLETE", 1))

    passed = 0
    for name, d, want_verdict, want_rc in cases:
        got_verdict, got_rc = run_audit(d, d)
        ok = (got_verdict == want_verdict and got_rc == want_rc)
        print("  self-test %-10s want=%-36s/%d got=%-36s/%d %s"
              % (name, want_verdict, want_rc, got_verdict, got_rc,
                 "PASS" if ok else "FAIL"))
        if ok:
            passed += 1
    print("AUDIT_RADIOML_NPU_AB SELF-TEST %d/%d" % (passed, len(cases)))
    return 0 if passed == len(cases) else 1


# ---------------------------------------------------------------------------
# main audit
# ---------------------------------------------------------------------------


def run_audit(out_dir, host_results):
    results_path = os.path.join(out_dir, "radioml_npu_ab_results.tsv")
    logits_path = os.path.join(out_dir, "radioml_npu_ab_logits.tsv")
    per_path = os.path.join(host_results, "host_inference", "per_sample_results.tsv")
    host_logits_path = os.path.join(host_results, "host_inference", "raw24_logits.tsv")
    sel_path = os.path.join(host_results, "frozen_test_selection.tsv")

    for p in (results_path, logits_path):
        if not os.path.isfile(p):
            return "MEASUREMENT_INCOMPLETE", 1
    for p in (per_path, host_logits_path, sel_path):
        if not os.path.isfile(p):
            fail("missing host reference: " + p)

    # ---- structural validation (any mismatch -> INCOMPLETE, fail-closed) ----
    def structural_error(msg):
        print("AUDIT_RADIOML_NPU_AB INCOMPLETE: " + msg, file=sys.stderr)
        return "MEASUREMENT_INCOMPLETE", 1

    board = read_tsv(results_path, RESULTS_HEADER, len(RESULTS_HEADER),
                     "board results")
    blogits = read_tsv(logits_path, LOGITS_HEADER, len(LOGITS_HEADER),
                       "board logits")
    host = read_tsv(per_path, PER_SAMPLE_HEADER, len(PER_SAMPLE_HEADER),
                    "host per_sample")
    hlogits = read_tsv(host_logits_path, LOGITS_HEADER, len(LOGITS_HEADER),
                       "host raw24_logits")
    sel = read_tsv(sel_path, SELECTION_HEADER, len(SELECTION_HEADER),
                   "frozen_test_selection")

    if len(board) != N_FRAMES:
        return structural_error("board results has %d rows (want %d)"
                                % (len(board), N_FRAMES))
    if len(blogits) != N_FRAMES:
        return structural_error("board logits has %d rows (want %d)"
                                % (len(blogits), N_FRAMES))
    if len(host) != N_FRAMES:
        return structural_error("host per_sample has %d rows (want %d)"
                                % (len(host), N_FRAMES))
    if len(hlogits) != N_FRAMES:
        return structural_error("host raw24_logits has %d rows (want %d)"
                                % (len(hlogits), N_FRAMES))
    if len(sel) != N_FRAMES:
        return structural_error("frozen_test_selection has %d rows (want %d)"
                                % (len(sel), N_FRAMES))

    # selection_id contiguous 1..480 + unique; hdf5_row_index unique.
    def sel_ids(rows):
        return [int(r[0]) for r in rows]
    for label, rows in (("board results", board), ("board logits", blogits)):
        ids = sel_ids(rows)
        if ids != list(range(1, N_FRAMES + 1)):
            return structural_error("%s selection_id not contiguous 1..480"
                                    % label)
    if len(set(int(r[1]) for r in board)) != N_FRAMES:
        return structural_error("board results hdf5_row_index not unique")

    # board rows: finite == 1, repeat_deterministic == 1, result_layer == NPU_BF16.
    for r in board:
        if r[5] != "1":
            return structural_error("selection_id %s finite != 1" % r[0])
        if r[8] != "1":
            return structural_error("selection_id %s repeat_deterministic != 1" % r[0])
        if r[15] != "NPU_BF16":
            return structural_error("selection_id %s result_layer != NPU_BF16 (got %s)"
                                    % (r[0], r[15]))
        for v in r[12:15]:
            if not is_finite(v):
                return structural_error("selection_id %s has non-finite top1/top2/margin"
                                        % r[0])

    # board logits: all 24 finite; pred_pass1/pred_pass2 consistent with results.
    board_logits_map = {}
    for r in blogits:
        sid = int(r[0])
        logits = [float(r[3 + c]) for c in range(N_CLASSES)]
        for v in logits:
            if not is_finite(v):
                return structural_error("selection_id %s has non-finite logit" % sid)
        board_logits_map[sid] = (logits, int(r[27]), int(r[28]))

    board_map = {}
    for r in board:
        sid = int(r[0])
        board_map[sid] = r
        if (board_logits_map[sid][1] != int(r[6]) or
                board_logits_map[sid][2] != int(r[7])):
            return structural_error(
                "selection_id %s: results pred_pass1/2 != logits pred_pass1/2" % sid)
        # argmax of board logits must equal npu_pred_pass1
        if int(max(range(N_CLASSES), key=lambda c: board_logits_map[sid][0][c])) != int(r[6]):
            return structural_error(
                "selection_id %s: logits argmax != npu_pred_pass1" % sid)

    # host reference keyed by hdf5_row_index (cross-check board host_pred).
    host_by_hri = {}
    for r in host:
        host_by_hri[int(r[1])] = r
    host_logits_by_hri = {}
    for r in hlogits:
        host_logits_by_hri[int(r[1])] = r

    for r in board:
        sid = int(r[0])
        hri = int(r[1])
        cls = int(r[2])
        if hri not in host_by_hri:
            return structural_error("selection_id %s: hdf5_row_index %d not in host"
                                    % (sid, hri))
        host_r = host_by_hri[hri]
        host_pred = int(host_r[6])
        if int(r[10]) != host_pred:
            return structural_error(
                "selection_id %s: board host_pred %s != host per_sample pred_pass1 %s"
                % (sid, r[10], host_pred))
        # selection identity cross-check (raw24_class / snr / modulation)
        if int(host_r[3]) != cls:
            return structural_error("selection_id %s: host raw24_class != board" % sid)
        if int(host_r[2]) != int(r[4]):
            return structural_error("selection_id %s: host snr_db != board snr_db"
                                    % sid)
        if host_r[4] != r[3]:
            return structural_error("selection_id %s: host modulation != board" % sid)

    # ---- agreement + accuracy ----
    total_correct = 0
    host_agree = 0
    per_snr = {s: {"total": 0, "correct": 0} for s in SNR_LEVELS}
    per_class = {c: {"total": 0, "correct": 0} for c in range(N_CLASSES)}
    per_class_snr = {}
    confusion = [[0] * N_CLASSES for _ in range(N_CLASSES)]
    disagreements = []
    logit_max_abs_diff = []
    logit_agree_count = 0

    for r in board:
        sid = int(r[0])
        hri = int(r[1])
        cls = int(r[2])
        snr = int(r[4])
        npu_pred = int(r[6])
        host_pred = int(r[10])
        correct = (npu_pred == cls)
        agree = (npu_pred == host_pred)
        if correct:
            total_correct += 1
        if agree:
            host_agree += 1
        per_snr[snr]["total"] += 1
        per_snr[snr]["correct"] += (1 if correct else 0)
        per_class[cls]["total"] += 1
        per_class[cls]["correct"] += (1 if correct else 0)
        key = (cls, snr)
        per_class_snr.setdefault(key, {"total": 0, "correct": 0})
        per_class_snr[key]["total"] += 1
        per_class_snr[key]["correct"] += (1 if correct else 0)
        confusion[cls][npu_pred] += 1

        bl, bp1, bp2 = board_logits_map[sid]
        hl = [float(host_logits_by_hri[hri][3 + c]) for c in range(N_CLASSES)]
        diffs = [abs(bl[c] - hl[c]) for c in range(N_CLASSES)]
        logit_max_abs_diff.append(max(diffs))
        host_argmax = int(max(range(N_CLASSES), key=lambda c: hl[c]))
        if host_argmax == npu_pred:
            logit_agree_count += 1

        if not agree:
            disagreements.append({
                "selection_id": sid, "hdf5_row_index": hri, "raw24_class": cls,
                "modulation": r[3], "snr_db": snr, "npu_pred": npu_pred,
                "host_pred": host_pred,
                "npu_top1_logit": float(r[12]), "npu_top2_logit": float(r[13]),
                "npu_margin": float(r[14]),
                "host_top1_logit": float(host_by_hri[hri][12]),
                "host_top2_logit": float(host_by_hri[hri][13]),
                "host_margin": float(host_by_hri[hri][14]),
                "max_abs_logit_diff": max(diffs),
            })

    # ---- verdict ----
    all_agree = (host_agree == N_FRAMES)
    verdict = ("MEASUREMENT_COMPLETE_HOST_MATCH" if all_agree
               else "MEASUREMENT_COMPLETE_HOST_DISAGREEMENT")

    # ---- write host audit outputs into the (copied) out dir ----
    report = {
        "verdict": verdict,
        "task": "fix10class24-original-radioml-npu-ab1",
        "deployment_mode": "RAW24_UNMERGED",
        "scored": N_FRAMES,
        "total_correct": total_correct,
        "label_accuracy": total_correct / N_FRAMES,
        "host_agree": host_agree,
        "host_agreement": host_agree / N_FRAMES,
        "logit_argmax_agree": logit_agree_count,
        "logit_max_abs_diff_max": max(logit_max_abs_diff),
        "logit_max_abs_diff_mean":
            sum(logit_max_abs_diff) / len(logit_max_abs_diff),
        "disagreement_count": N_FRAMES - host_agree,
        "per_snr": {str(s): {"accuracy": per_snr[s]["correct"] / per_snr[s]["total"],
                             "correct": per_snr[s]["correct"],
                             "total": per_snr[s]["total"]} for s in SNR_LEVELS},
    }
    with open(os.path.join(out_dir, "radioml_npu_ab_host_audit.json"), "w",
              encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)

    with open(os.path.join(out_dir, "radioml_npu_ab_host_audit_disagreements.tsv"),
              "w", encoding="utf-8", newline="") as f:
        f.write("selection_id\thdf5_row_index\traw24_class\tmodulation\tsnr_db\t"
                "npu_pred\thost_pred\tnpu_top1_logit\tnpu_top2_logit\tnpu_margin\t"
                "host_top1_logit\thost_top2_logit\thost_margin\tmax_abs_logit_diff\n")
        for d in disagreements:
            f.write("\t".join(str(d[k]) for k in (
                "selection_id", "hdf5_row_index", "raw24_class", "modulation",
                "snr_db", "npu_pred", "host_pred", "npu_top1_logit",
                "npu_top2_logit", "npu_margin", "host_top1_logit",
                "host_top2_logit", "host_margin", "max_abs_logit_diff")) + "\n")

    with open(os.path.join(out_dir, "radioml_npu_ab_host_audit_confusion.tsv"),
              "w", encoding="utf-8", newline="") as f:
        f.write("true_class\t" + "\t".join(LABEL_ORDER) + "\n")
        for c in range(N_CLASSES):
            f.write(LABEL_ORDER[c] + "\t" + "\t".join(str(confusion[c][p])
                                                      for p in range(N_CLASSES)) + "\n")

    with open(os.path.join(out_dir, "radioml_npu_ab_host_audit_per_class_snr.tsv"),
              "w", encoding="utf-8", newline="") as f:
        f.write("raw24_class\tmodulation\tsnr_db\ttotal\tcorrect\taccuracy\n")
        for c in range(N_CLASSES):
            for s in SNR_LEVELS:
                e = per_class_snr[(c, s)]
                f.write("%d\t%s\t%d\t%d\t%d\t%.4f\n"
                        % (c, LABEL_ORDER[c], s, e["total"], e["correct"],
                           e["correct"] / e["total"]))

    print("AUDIT_RADIOML_NPU_AB %s scored=%d correct=%d label_accuracy=%.6f "
          "host_agree=%d host_agreement=%.6f logit_argmax_agree=%d "
          "logit_max_abs_diff_max=%.6g disagreements=%d"
          % (verdict, N_FRAMES, total_correct, total_correct / N_FRAMES,
             host_agree, host_agree / N_FRAMES, logit_agree_count,
             max(logit_max_abs_diff), len(disagreements)))
    print("AUDIT_RADIOML_NPU_AB per_snr " +
          " ".join("snr%d=%.4f(%d/%d)" % (s, per_snr[s]["correct"] / per_snr[s]["total"],
                                           per_snr[s]["correct"], per_snr[s]["total"])
                   for s in SNR_LEVELS))
    for d in disagreements:
        print("AUDIT_RADIOML_NPU_AB_DISAGREE sid=%d hri=%d %s@%ddB npu=%d(%s) "
              "host=%d(%s) npu_margin=%.4f host_margin=%.4f max_logit_diff=%.6g"
              % (d["selection_id"], d["hdf5_row_index"], d["modulation"], d["snr_db"],
                 d["npu_pred"], LABEL_ORDER[d["npu_pred"]],
                 d["host_pred"], LABEL_ORDER[d["host_pred"]],
                 d["npu_margin"], d["host_margin"], d["max_abs_logit_diff"]))

    # Both HOST_MATCH and HOST_DISAGREEMENT are completed measurements (rc=0);
    # only structural problems above returned INCOMPLETE (rc=1).
    return verdict, 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir",
                    help="the (copied) board $OUT dir containing the 3 board files")
    ap.add_argument("--host-results", default=DEFAULT_HOST_RESULTS,
                    help="accuracy1 results dir (frozen_test_selection.tsv + host_inference/)")
    ap.add_argument("--self-test", action="store_true",
                    help="run synthetic fixtures and exit")
    args = ap.parse_args()

    if args.self_test:
        sys.exit(self_test())

    if not args.out_dir:
        ap.error("--out-dir is required (unless --self-test)")
    verdict, rc = run_audit(args.out_dir, args.host_results)
    sys.exit(rc)


if __name__ == "__main__":
    main()
