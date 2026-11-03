#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
judge_radioml_blind_clean.py -- fix10class24-dualsdr-blind-clean1 offline judger.

Consumes the blind TX package (source_index -> true class), the digital no-RF replay
(THREE-LAYER: A original / B digital-preprocessed / B' rotated-window), and the board's
board_results.tsv (C = real-RF board measurement), and reports:

  SIX frozen statistics (unchanged):
    1. completion_of_24_samples        all 24 source_index present (failures stay)
    2. e2e_correct_over_24             finite && raw24_pred == class, /24
    3. accuracy_plus_coverage          coverage = finite/24; gated acc = correct/finite
    4. per_class_confusion_anomaly     per-class correct + confusion + anomaly flags
    5. digital_vs_real_rf              board vs digital (exact/rotated) predictions
    6. negative_control_result         source_index 0 (TX off) outcome

  PLUS the coordinator's three-layer / conclusion-routing analysis:
    * three-layer comparison:  A (original, offline-only) -> B (digital preprocessed)
      -> C (board real RF), same batch + same frozen model, per-layer accuracy.
    * per-layer flips:         A->B (preprocessing/quantization), B->C (RF chain).
    * conclusion routing:       WHERE errors first appear -- preprocessing / RF recovery
      chain / post-recovery model robustness -- ranked by evidence, with
      "to confirm" where evidence is insufficient and NO single attribution guaranteed.

Honest red lines (never violated):
  * The board NEVER knows the class; the judger alone maps source_index -> class from
    the PC's blind_tx_manifest.tsv.
  * A board row whose status != "ok" (e.g. non_finite / capture_anomaly / rx_clipped)
    is an end-to-end FAILURE and STAYS in the denominator (never auto-success).
  * A missing source_index is incomplete/PENDING, never auto-success.
  * The board NEVER forces a classification: there is no gate, so raw24_pred is always
    the finite argmax over 24 logits (or -1 when non-finite).
  * The original reference IQ (layer A) is used ONLY for offline analysis; it never
    enters the RX inference path (blind red line).
  * This is a MEASUREMENT, not a regression PASS.  The judger reports numbers + a
    summary verdict token, but never fabricates RF_PASS / HOST_MATCH, and never
    hard-codes a single root-cause attribution.
  * No auto-expansion this round: multi-tap equalization / zero-frequency-avoidance
    transmission / RF fine-tuning are listed as EVIDENCE-GATED CANDIDATES ONLY, to be
    run as separate A/B later, never added to this measurement.

Usage:
    python -I scripts/judge_radioml_blind_clean.py \
        --tx-dir <blind tx package> \
        [--board-results <board_results.tsv>] \
        [--digital <digital_replay.tsv>] \
        --out-dir <fresh dir>
    python -I scripts/judge_radioml_blind_clean.py --self-test
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_blind_clean_contract as BC  # noqa: E402
import digital_replay_radioml_blind_clean as DR  # noqa: E402  (REPLAY_HEADER)

TOKEN = "M29-RML24-FIX10CLASS24-DUALSDR-BLIND-CLEAN1-JUDGED"

BOARD_COLS = [
    "run_id", "source_index", "capture_time_us", "finite", "repeat_deterministic",
    "raw24_pred", "raw24_margin", "clip", "overflow", "dropped", "discontinuity",
    "short_block", "timeouts", "training_residual", "training_gate",
    "model_input_sha256", "model_sha", "rx_sample_rate", "rx_lo", "rx_bw",
    "rx_gain", "status",
]


def load_tx_manifest(tx_dir: Path):
    path = tx_dir / "blind_tx_manifest.tsv"
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].rstrip("\n").split("\t")
    assert header == BC.MANIFEST_HEADER
    m = {}
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.rstrip("\n").split("\t")
        m[int(f[0])] = {"class_index": int(f[1]), "class_name": f[2]}
    assert sorted(m) == list(range(1, 25))
    return m


def _tsv_rows(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        return None
    header = lines[0].rstrip("\n").split("\t")
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        rows.append(ln.rstrip("\n").split("\t"))
    return header, rows


def load_board_tsv(path: Path):
    """board_results.tsv keyed by source_index (column 1; column 0 = run_id)."""
    if path is None or not path.is_file():
        return None
    parsed = _tsv_rows(path)
    if parsed is None:
        return None
    header, rows = parsed
    assert header == BOARD_COLS, "board_results.tsv header mismatch"
    return {int(f[1]): dict(zip(header, f)) for f in rows}


def load_digital_tsv(path: Path):
    """digital_replay.tsv keyed by source_index (column 0)."""
    if path is None or not path.is_file():
        return None
    parsed = _tsv_rows(path)
    if parsed is None:
        return None
    header, rows = parsed
    assert header == DR.REPLAY_HEADER, "digital_replay.tsv header mismatch"
    return {int(f[0]): dict(zip(header, f)) for f in rows}


def _i(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def compute(tx_manifest, board, digital):
    per = {}
    for sid in range(1, 25):
        ci = tx_manifest[sid]["class_index"]
        name = tx_manifest[sid]["class_name"]
        b = board.get(sid) if board else None
        d = digital.get(sid) if digital else None
        rec = {
            "sid": sid, "class_index": ci, "class_name": name,
            "board_present": b is not None,
            "board_pred": _i(b["raw24_pred"]) if b else None,
            "board_finite": (_i(b["finite"]) == 1) if b else None,
            "board_status": b["status"] if b else None,
            "board_margin": float(b["raw24_margin"]) if b and b["raw24_margin"] else None,
            "digital_present": d is not None,
            "digital_orig_pred": _i(d["orig_pred"]) if d else None,
            "digital_exact_pred": _i(d["exact_pred"]) if d else None,
            "digital_rotated_pred": _i(d["rotated_pred"]) if d else None,
        }
        per[sid] = rec
    return per


def e2e_correct(rec):
    """End-to-end correct: board finite AND status ok AND pred == class."""
    if not rec["board_present"] or not rec["board_finite"]:
        return False
    if rec["board_status"] != "ok":
        return False
    return rec["board_pred"] == rec["class_index"]


def route_conclusion(per, digital, board):
    """Three-layer comparison + evidence-ranked conclusion routing.

    A = original clean reference (offline only), B = digital preprocessed,
    C = board real RF.  Reports per-layer accuracy, A->B / B->C flips, and WHERE
    errors first appear -- WITHOUT guaranteeing a single attribution.
    """
    n = 24
    a_correct = sum(1 for s in range(1, n + 1)
                    if per[s]["digital_orig_pred"] == per[s]["class_index"])
    b_correct = sum(1 for s in range(1, n + 1)
                    if per[s]["digital_exact_pred"] == per[s]["class_index"])
    b_rot_correct = sum(1 for s in range(1, n + 1)
                        if per[s]["digital_rotated_pred"] == per[s]["class_index"])
    c_correct = sum(1 for s in range(1, n + 1) if e2e_correct(per[s])) if board else None

    a_to_b_flips = sum(1 for s in range(1, n + 1)
                       if per[s]["digital_orig_pred"] is not None and
                       per[s]["digital_exact_pred"] is not None and
                       per[s]["digital_orig_pred"] != per[s]["digital_exact_pred"])
    # B->C: board finite rows whose board pred differs from the digital exact pred.
    b_to_c_flips = None
    if board:
        b_to_c_flips = sum(1 for s in range(1, n + 1)
                           if per[s]["board_finite"] and
                           per[s]["digital_exact_pred"] is not None and
                           per[s]["board_pred"] != per[s]["digital_exact_pred"])

    layers = {
        "A_original_clean_reference": {"correct": a_correct, "total": n,
                                       "note": "offline reference only; not in RX path"},
        "B_digital_preprocessed": {"correct": b_correct, "total": n,
                                   "note": "quantization roundtrip"},
        "B_rotated_window": {"correct": b_rot_correct, "total": n,
                             "note": "frozen blind window (capture phase 0)"},
        "C_board_real_rf": ({"correct": c_correct, "total": n,
                             "note": "e2e: finite && status ok && pred == class"}
                            if c_correct is not None else None),
    }

    # Evidence-ranked findings (most upstream stage first).
    findings = []
    if digital is None:
        findings.append({"stage": "digital_reference",
                         "status": "missing",
                         "detail": "no digital replay supplied; three-layer A/B "
                                   "comparison unavailable."})
    else:
        if a_correct < n:
            findings.append({
                "stage": "post_recovery_model_robustness",
                "status": "implicated",
                "evidence": "A original clean %d/%d correct -- the frozen model "
                            "misclassifies the clean original domain itself." %
                            (a_correct, n),
            })
        if a_to_b_flips > 0:
            findings.append({
                "stage": "preprocessing_quantization",
                "status": "implicated",
                "evidence": "A->B flips %d -- CI16 quantization changes %d prediction(s)."
                            % (a_to_b_flips, a_to_b_flips),
            })
        if b_rot_correct < n and a_to_b_flips == 0:
            findings.append({
                "stage": "window_rotation",
                "status": "implicated",
                "evidence": "B rotated %d/%d vs B exact %d/%d -- the frozen window "
                            "offset alone flips prediction(s)." %
                            (b_rot_correct, n, b_correct, n),
            })
    if board is None:
        findings.append({"stage": "rf_recovery_chain",
                         "status": "insufficient_evidence",
                         "detail": "board results pending; C layer not judged yet."})
    else:
        if c_correct is not None and c_correct < n:
            findings.append({
                "stage": "rf_recovery_chain_or_rf_robustness",
                "status": "implicated",
                "evidence": "C board real-RF %d/%d correct -- errors appear across the "
                            "RF link (analog IQ imbalance / CFO / gain / capture "
                            "phase)." % (c_correct, n),
            })
        if b_to_c_flips is not None and b_to_c_flips > 0:
            findings.append({
                "stage": "rf_recovery_chain",
                "status": "implicated",
                "evidence": "B->C flips %d (among finite board rows) -- the real-RF "
                            "chain changes prediction(s) vs the digital reference." %
                            b_to_c_flips,
            })

    if not findings:
        findings.append({"stage": "none", "status": "no_error_observed",
                         "detail": "all supplied layers correct."})

    # First failure stage = the most upstream implicated stage, if any.
    order = ["post_recovery_model_robustness", "preprocessing_quantization",
             "window_rotation", "rf_recovery_chain_or_rf_robustness",
             "rf_recovery_chain"]
    first = None
    for stage in order:
        if any(f.get("stage") == stage and f.get("status") == "implicated"
               for f in findings):
            first = stage
            break

    return {
        "layers": layers,
        "flips": {"A_to_B_preprocessing": a_to_b_flips,
                  "B_to_C_rf": b_to_c_flips},
        "findings": findings,
        "first_failure_stage": first,
        "no_single_attribution_guaranteed": True,
        "evidence_note": ("24 samples = one per class; a small sample set. "
                          "Multiple stages may contribute; attribution is ranked by "
                          "evidence, not proven unique."),
        "candidates_not_applied_this_round": [
            "multi-tap equalization",
            "zero-frequency-avoidance transmission",
            "RF fine-tuning (separate A/B)",
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tx-dir", default="")
    ap.add_argument("--board-results", default="")
    ap.add_argument("--digital", default="")
    ap.add_argument("--out-dir", default="")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.tx_dir or not args.out_dir:
        ap.error("--tx-dir and --out-dir are required (or --self-test)")

    out_dir = Path(args.out_dir)
    if out_dir.exists():
        raise SystemExit("ERROR: --out-dir already exists: %s" % out_dir)
    out_dir.mkdir(parents=True)

    tx_manifest = load_tx_manifest(Path(args.tx_dir))
    board = load_board_tsv(Path(args.board_results)) if args.board_results else None
    digital = load_digital_tsv(Path(args.digital)) if args.digital else None

    per = compute(tx_manifest, board, digital)

    # ---- 1. completion of 24 samples ----
    present = [s for s in range(1, 25) if per[s]["board_present"]]
    completion = {
        "present": len(present),
        "missing": sorted(set(range(1, 25)) - set(present)),
        "complete": len(present) == 24,
    }

    # ---- 2. e2e correct over 24 (failures stay in denominator) ----
    correct = sum(1 for s in range(1, 25) if e2e_correct(per[s]))
    e2e = {"correct": correct, "total": 24, "failures_stay_in_denominator": True}

    # ---- 3. accuracy + coverage ----
    finite = sum(1 for s in range(1, 25) if per[s]["board_finite"])
    gated_correct = sum(1 for s in range(1, 25)
                        if per[s]["board_finite"] and per[s]["board_pred"] == per[s]["class_index"])
    acc_cov = {
        "coverage": finite / 24.0 if board else None,
        "gated_accuracy": (gated_correct / finite) if (board and finite) else None,
        "end_to_end_accuracy": correct / 24.0 if board else None,
    }

    # ---- 4. per-class confusion + anomaly ----
    conf = np.zeros((24, 24), dtype=np.int64)
    for s in range(1, 25):
        rec = per[s]
        if rec["board_finite"] and rec["board_pred"] is not None:
            conf[rec["class_index"], rec["board_pred"]] += 1
    per_class = {}
    for ci in range(24):
        name = BC.LABEL_ORDER_24[ci]
        rs = [per[s] for s in range(1, 25) if per[s]["class_index"] == ci]
        n = len(rs)
        present_n = sum(1 for r in rs if r["board_present"])
        correct_n = sum(1 for r in rs if e2e_correct(r))
        preds = [r["board_pred"] for r in rs if r["board_finite"]]
        per_class[name] = {
            "n": n, "present": present_n, "e2e_correct": correct_n,
            "finite_preds": preds,
        }
    anomalies = []
    for ci in range(24):
        name = BC.LABEL_ORDER_24[ci]
        preds = [p for p in per_class[name]["finite_preds"] if p is not None]
        if preds and all(p != ci for p in preds) and len(set(preds)) == 1:
            anomalies.append({"class": name, "collapsed_to": preds[0]})

    # ---- 5. digital vs real RF ----
    digital_vs_rf = {
        "digital_present": digital is not None,
        "board_vs_digital_exact_flips": None,
        "board_vs_digital_rotated_flips": None,
        "digital_exact_correct": None,
        "digital_rotated_correct": None,
    }
    if digital:
        d_exact_correct = sum(1 for s in range(1, 25)
                              if per[s]["digital_exact_pred"] == per[s]["class_index"])
        d_rot_correct = sum(1 for s in range(1, 25)
                            if per[s]["digital_rotated_pred"] == per[s]["class_index"])
        digital_vs_rf["digital_exact_correct"] = d_exact_correct
        digital_vs_rf["digital_rotated_correct"] = d_rot_correct
        if board:
            flips_exact = sum(1 for s in range(1, 25)
                              if per[s]["board_finite"] and
                              per[s]["digital_exact_pred"] is not None and
                              per[s]["board_pred"] != per[s]["digital_exact_pred"])
            flips_rot = sum(1 for s in range(1, 25)
                            if per[s]["board_finite"] and
                            per[s]["digital_rotated_pred"] is not None and
                            per[s]["board_pred"] != per[s]["digital_rotated_pred"])
            digital_vs_rf["board_vs_digital_exact_flips"] = flips_exact
            digital_vs_rf["board_vs_digital_rotated_flips"] = flips_rot

    # ---- 6. negative control result ----
    neg = board.get(0) if board else None
    negative_control = {
        "present": neg is not None,
        "raw24_pred": _i(neg["raw24_pred"]) if neg else None,
        "finite": (_i(neg["finite"]) == 1) if neg else None,
        "status": neg["status"] if neg else None,
        "note": "source_index 0 = TX off; raw24_pred is the noise-floor classification "
                "(no OOD head -- any class is 'valid' structurally; this just proves "
                "the blind measurement infrastructure ran with TX off).",
    }

    conclusion = route_conclusion(per, digital, board)

    board_pending = board is None
    summary = {
        "token": TOKEN,
        "board_pending": board_pending,
        "six_statistics": {
            "completion_of_24_samples": completion,
            "e2e_correct_over_24": e2e,
            "accuracy_plus_coverage": acc_cov,
            "per_class_confusion_anomaly": {
                "per_class": per_class,
                "collapsed_anomalies": anomalies,
            },
            "digital_vs_real_rf": digital_vs_rf,
            "negative_control_result": negative_control,
        },
        "three_layer_conclusion_routing": conclusion,
        "note": ("board never knows class; status!=ok is e2e failure and stays in "
                 "denominator; missing=incomplete/PENDING; board never forces; "
                 "original reference IQ is offline-only (never in RX path); "
                 "no single root-cause attribution guaranteed; no auto-expansion "
                 "this round. Measurement, not a regression PASS."),
    }
    with open(out_dir / "judge_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    if board:
        with open(out_dir / "confusion_board.tsv", "w", encoding="utf-8") as f:
            f.write("true_class\t" + "\t".join(BC.LABEL_ORDER_24) + "\n")
            for i in range(24):
                f.write(BC.LABEL_ORDER_24[i] + "\t" +
                        "\t".join(str(conf[i, j]) for j in range(24)) + "\n")

    def fmt(x):
        return ("%.4f" % x) if x is not None else "PENDING"
    print("RADIOML_BLIND_CLEAN1_JUDGE board_pending=%s completion=%d/24 "
          "e2e_correct=%d/24 coverage=%s gated_acc=%s e2e_acc=%s "
          "A=%s B=%s C=%s first_failure=%s anomalies=%d out_dir=%s" %
          (board_pending, completion["present"], correct,
           fmt(acc_cov["coverage"]), fmt(acc_cov["gated_accuracy"]),
           fmt(acc_cov["end_to_end_accuracy"]),
           ("%d/24" % conclusion["layers"]["A_original_clean_reference"]["correct"]
            if digital else "PENDING"),
           ("%d/24" % conclusion["layers"]["B_digital_preprocessed"]["correct"]
            if digital else "PENDING"),
           (fmt(correct / 24.0) if board else "PENDING"),
           conclusion["first_failure_stage"] or "none",
           len(anomalies), out_dir))
    print("RADIOML_BLIND_CLEAN1_JUDGE_DONE")
    return 0


def self_test() -> int:
    checks = []
    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print("SELF-TEST %-48s %s%s" % (name, "PASS" if ok else "FAIL",
                                        (" -- " + detail) if detail else ""))

    import tempfile
    with tempfile.TemporaryDirectory() as td:
        d = Path(td)
        tx = d / "tx"
        BC.write_tx_package(tx)
        tx_manifest = load_tx_manifest(tx)
        check("tx manifest: 24 source_index -> class", len(tx_manifest) == 24)

        # Build a synthetic board_results.tsv: 24 rows, all correct.
        header = "\t".join(BOARD_COLS)
        rows = []
        for s in range(1, 25):
            ci = tx_manifest[s]["class_index"]
            rows.append("\t".join([
                "blind-test", str(s), "1000", "1", "1", str(ci), "0.5",
                "0", "0", "0", "0", "0", "0", "NA", "NOT_APPLICABLE",
                "0" * 64, "c1781aec", "2560000", "2400000000", "18000000",
                "35.0", "ok"]))
        rows.append("\t".join(["blind-test", "0", "0", "1", "1", "5", "0.1",
                               "0", "0", "0", "0", "0", "0", "NA", "NOT_APPLICABLE",
                               "0" * 64, "c1781aec", "2560000", "2400000000",
                               "18000000", "35.0", "ok"]))
        board_path = d / "board_results.tsv"
        board_path.write_text(header + "\n" + "\n".join(rows) + "\n",
                              encoding="utf-8")
        board = load_board_tsv(board_path)
        check("board keyed by source_index (run_id col ignored)",
              sorted(board) == list(range(25)))
        per = compute(tx_manifest, board, None)
        check("compute: 24 rows, board present", all(per[s]["board_present"]
                                                     for s in range(1, 25)))
        check("e2e correct: 24/24 (all-correct synthetic)",
              sum(1 for s in range(1, 25) if e2e_correct(per[s])) == 24)
        check("negative control present", board.get(0) is not None)

        # A row with status != ok must FAIL e2e (stays in denominator).
        per2 = dict(per)
        per2[1] = dict(per[1], board_status="capture_anomaly")
        check("status!=ok is e2e failure", not e2e_correct(per2[1]))

        # Build a synthetic digital replay (all layers correct) and route.
        dheader = "\t".join(DR.REPLAY_HEADER)
        drows = []
        for s in range(1, 25):
            ci = tx_manifest[s]["class_index"]
            drows.append("\t".join([
                str(s), str(ci), BC.LABEL_ORDER_24[ci],
                str(ci), "1",   # orig_pred, orig_correct
                str(ci), "1",   # exact_pred, exact_correct
                str(ci), "1",   # rotated_pred, rotated_correct
                "1",            # finite
                "1.0", "0.0", "0.0",   # orig rms/dc
                "1.0", "0.0", "0.0",   # exact rms/dc
                "1.0", "0.0", "0.0",   # rotated rms/dc
                "0.99999", "0.0035",   # corr/resid
                "0" * 64,               # model_input_sha256
            ]))
        digital_path = d / "digital_replay.tsv"
        digital_path.write_text(dheader + "\n" + "\n".join(drows) + "\n",
                                encoding="utf-8")
        digital = load_digital_tsv(digital_path)
        check("digital keyed by source_index", sorted(digital) == list(range(1, 25)))
        per3 = compute(tx_manifest, board, digital)
        concl = route_conclusion(per3, digital, board)
        check("all-correct synthetic -> no failure stage",
              concl["first_failure_stage"] is None
              and concl["layers"]["A_original_clean_reference"]["correct"] == 24
              and concl["flips"]["A_to_B_preprocessing"] == 0)
        check("conclusion routing has no-auto-expansion candidates",
              concl["candidates_not_applied_this_round"] == [
                  "multi-tap equalization",
                  "zero-frequency-avoidance transmission",
                  "RF fine-tuning (separate A/B)",
              ])

    all_ok = all(checks)
    print("RADIOML_BLIND_CLEAN1_JUDGE_SELF_TEST %s (%d/%d)" %
          ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
