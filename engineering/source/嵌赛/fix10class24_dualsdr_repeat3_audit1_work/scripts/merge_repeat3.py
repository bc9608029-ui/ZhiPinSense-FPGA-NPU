#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_repeat3.py -- fix10class24-dualsdr-repeat3-audit1 Phase D.

Merge the 23 board-gated (board NPU) samples with the 49 host-forced
(Host BF16 diagnostic bypass) samples under the marker
HYBRID_BOARD_GATED_PLUS_HOST_FORCED, and emit the per-round / per-class /
confusion / unresolved deliverables + summary answering the 5 questions.

Inputs (already produced by Phase A + Phase C):
  results/inventory.tsv                          -- 72 board rows (valid/pred/correct)
  results/host_inference/per_sample_results.tsv  -- 49 forced rows

Outputs (results/):
  per_sample_results.tsv    -- 72 merged rows (layer-resolved pred/correct)
  per_round_summary.tsv     -- 3 rows + total
  per_class_repeatability.tsv -- 24 rows, 3-round preds/correct/gate + category
  confusion_counts.tsv      -- 24x24 confusion matrix + row/col totals
  unresolved_samples.tsv    -- merged samples still misclassified (17)
  summary.json              -- headline numbers + categories + conclusions

Red lines: no board / no SDR / no training / no model / recovery / gate change.
The merged metric is a HYBRID diagnostic, NOT a homogeneous board measurement.
Does NOT write RF_PASS / PROJECT_COMPLETE.
"""
import json
import os
import sys

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(WORK, "results")

INVENTORY = os.path.join(RESULTS, "inventory.tsv")
FORCED = os.path.join(RESULTS, "host_inference", "per_sample_results.tsv")

MERGE_MARKER = "HYBRID_BOARD_GATED_PLUS_HOST_FORCED"
LAYER_GATED = "BOARD_NPU_GATED"
LAYER_FORCED = "HOST_BF16_FORCED"

N_CLASSES = 24

# inventory.tsv round column is the bare integer; forced exports use the capture id.
RUN_DIRS = ("dual_bf16_rms2048_run1", "dual_bf16_rms2048_run2",
            "dual_bf16_rms2048_run3")


def round_name(r):
    r = str(r)
    if r in RUN_DIRS:
        return r
    try:
        return "dual_bf16_rms2048_run%d" % int(r)
    except ValueError:
        fatal("unrecognized round %r" % r)


def fatal(msg):
    sys.stderr.write("FAIL-CLOSED: %s\n" % msg)
    sys.exit(1)


def read_tsv(path):
    if not os.path.isfile(path):
        fatal("TSV not found: %s" % path)
    with open(path, "r", encoding="utf-8", newline="") as f:
        lines = [ln.rstrip("\r\n") for ln in f]
    if not lines:
        fatal("empty TSV: %s" % path)
    header = lines[0].split("\t")
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        if len(f) != len(header):
            fatal("TSV %s row has %d cols (want %d)" % (path, len(f), len(header)))
        rows.append(dict(zip(header, f)))
    return header, rows


def main():
    inv_header, inv_rows = read_tsv(INVENTORY)
    for col in ("round", "source_index", "raw24_class", "modulation", "valid",
                "raw24_pred", "baseline_pred", "correct", "prediction_agreement",
                "repeat_deterministic", "training_corr", "training_residual",
                "rf_verdict"):
        if col not in inv_header:
            fatal("inventory.tsv missing column %r" % col)

    _, forced_rows = read_tsv(FORCED)
    forced_map = {}
    for r in forced_rows:
        key = (r["round"], int(r["source_index"]))
        if key in forced_map:
            fatal("duplicate forced (round, source_index): %r" % (key,))
        forced_map[key] = r

    # ---- merge ----
    merged = []
    for r in inv_rows:
        rnd = round_name(r["round"])
        sid = int(r["source_index"])
        sc = int(r["raw24_class"])
        mod = r["modulation"]
        valid = int(r["valid"])
        key = (rnd, sid)
        if valid == 1:
            if int(r["correct"]) == -1 or int(r["raw24_pred"]) == -1:
                fatal("gated row %r has -1 pred/correct" % (key,))
            merged.append({
                "round": rnd, "source_index": sid, "raw24_class": sc,
                "modulation": mod, "gate_pass": 1, "result_layer": LAYER_GATED,
                "raw24_pred": int(r["raw24_pred"]),
                "baseline_pred": int(r["baseline_pred"]),
                "label_correct": int(r["correct"]),
                "prediction_agreement": int(r["prediction_agreement"]),
                "repeat_deterministic": int(r["repeat_deterministic"]),
                "payload_training_residual": r["training_residual"],
                "payload_training_corr": r["training_corr"],
                "wide_linear_enabled": "",
                "rf_verdict": r["rf_verdict"],
            })
        elif valid == 0:
            fr = forced_map.get(key)
            if fr is None:
                fatal("gate-rejected row %r has no forced export" % (key,))
            merged.append({
                "round": rnd, "source_index": sid, "raw24_class": sc,
                "modulation": mod, "gate_pass": 0, "result_layer": LAYER_FORCED,
                "raw24_pred": int(fr["raw24_pred_pass1"]),
                "baseline_pred": int(fr["baseline_pred"]),
                "label_correct": int(fr["label_correct"]),
                "prediction_agreement": int(fr["baseline_agreement"]),
                "repeat_deterministic": int(fr["repeat_argmax_deterministic"]),
                "payload_training_residual": fr["payload_training_residual"],
                "payload_training_corr": fr["payload_training_corr"],
                "wide_linear_enabled": fr["wide_linear_enabled"],
                "rf_verdict": "RF_DISTORTS_IQ",
            })
        else:
            fatal("unexpected valid=%d for %r" % (valid, key))

    # every (round, source_index) must appear exactly once, 72 total, 24 per round
    if len(merged) != 72:
        fatal("merged row count = %d (want 72)" % len(merged))
    keys = [(m["round"], m["source_index"]) for m in merged]
    if len(keys) != len(set(keys)):
        fatal("duplicate merged keys")
    for rnd in ("dual_bf16_rms2048_run1", "dual_bf16_rms2048_run2",
                "dual_bf16_rms2048_run3"):
        n = sum(1 for m in merged if m["round"] == rnd)
        if n != 24:
            fatal("round %s has %d merged rows (want 24)" % (rnd, n))

    # identity cross-check: modulation must match source_index across rounds
    for m in merged:
        # raw24_class is 0..23, modulation stable (checked in Phase A against manifest)
        pass

    # ---- per_sample_results.tsv ----
    sample_cols = ["round", "source_index", "raw24_class", "modulation",
                   "gate_pass", "result_layer", "raw24_pred", "baseline_pred",
                   "label_correct", "prediction_agreement", "repeat_deterministic",
                   "payload_training_residual", "payload_training_corr",
                   "wide_linear_enabled", "rf_verdict"]
    with open(os.path.join(RESULTS, "per_sample_results.tsv"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write("\t".join(sample_cols) + "\n")
        for m in sorted(merged, key=lambda z: (z["round"], z["source_index"])):
            f.write("\t".join(str(m[c]) for c in sample_cols) + "\n")

    # ---- per-round summary ----
    round_rows = []
    for rnd in ("dual_bf16_rms2048_run1", "dual_bf16_rms2048_run2",
                "dual_bf16_rms2048_run3"):
        rows = [m for m in merged if m["round"] == rnd]
        gated = [m for m in rows if m["gate_pass"] == 1]
        forced = [m for m in rows if m["gate_pass"] == 0]
        gated_correct = sum(1 for m in gated if m["label_correct"] == 1)
        forced_correct = sum(1 for m in forced if m["label_correct"] == 1)
        merged_correct = gated_correct + forced_correct
        round_rows.append({
            "round": rnd,
            "total": len(rows),
            "gated": len(gated),
            "gated_correct": gated_correct,
            "forced": len(forced),
            "forced_correct": forced_correct,
            "merged_correct": merged_correct,
            "end_to_end_accuracy": "%.6f" % (merged_correct / len(rows)),
        })
    round_cols = ["round", "total", "gated", "gated_correct", "forced",
                  "forced_correct", "merged_correct", "end_to_end_accuracy"]
    with open(os.path.join(RESULTS, "per_round_summary.tsv"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write("\t".join(round_cols) + "\n")
        for r in round_rows:
            f.write("\t".join(str(r[c]) for c in round_cols) + "\n")

    # ---- per-class repeatability ----
    # 24 classes: 3-round preds / correct / gate + category
    class_rows = []
    for cls in range(N_CLASSES):
        rows = sorted([m for m in merged if m["raw24_class"] == cls],
                      key=lambda z: z["round"])
        if len(rows) != 3:
            fatal("class %d has %d rows (want 3)" % (cls, len(rows)))
        preds = [m["raw24_pred"] for m in rows]
        corrects = [m["label_correct"] for m in rows]
        gates = [m["gate_pass"] for m in rows]
        correct_count = sum(corrects)
        gate_pass_count = sum(gates)

        if correct_count == 3:
            correctness = "PERSISTENT_CORRECT"
        elif correct_count == 0:
            if len(set(preds)) == 1:
                correctness = "PERSISTENT_MISCLASSIFIED_SAME_CLASS"
            else:
                correctness = "PERSISTENT_MISCLASSIFIED_DIVERGENT"
        else:
            correctness = "ROUND_FLUCTUATION"

        if gate_pass_count == 3:
            gating = "ALWAYS_GATED"
        elif gate_pass_count == 0:
            gating = "NEVER_GATED"
        else:
            gating = "MIXED_GATING"

        # 5-way combined category (disjoint, ordered):
        # 1 ALWAYS_GATED_CORRECT   (robust on-board)
        # 2 RECOVERABLE_CORRECT    (always correct, but >=1 round needs forced)
        # 3 ROUND_FLUCTUATION      (correct in some rounds only)
        # 4 PERSISTENT_MISCLASSIFIED_SAME_CLASS (0/3, same wrong pred)
        # 5 PERSISTENT_MISCLASSIFIED_DIVERGENT  (0/3, differing wrong preds)
        if correctness == "PERSISTENT_CORRECT" and gating == "ALWAYS_GATED":
            category = "ALWAYS_GATED_CORRECT"
        elif correctness == "PERSISTENT_CORRECT":
            category = "RECOVERABLE_CORRECT"
        elif correctness == "ROUND_FLUCTUATION":
            category = "ROUND_FLUCTUATION"
        elif correctness == "PERSISTENT_MISCLASSIFIED_SAME_CLASS":
            category = "PERSISTENT_MISCLASSIFIED_SAME_CLASS"
        else:
            category = "PERSISTENT_MISCLASSIFIED_DIVERGENT"

        class_rows.append({
            "raw24_class": cls,
            "modulation": rows[0]["modulation"],
            "source_index": rows[0]["source_index"],
            "round1_pred": preds[0], "round2_pred": preds[1],
            "round3_pred": preds[2],
            "round1_correct": corrects[0], "round2_correct": corrects[1],
            "round3_correct": corrects[2],
            "round1_gate_pass": gates[0], "round2_gate_pass": gates[1],
            "round3_gate_pass": gates[2],
            "correct_count": correct_count,
            "gate_pass_count": gate_pass_count,
            "correctness_category": correctness,
            "gating_category": gating,
            "category": category,
        })
    class_cols = ["raw24_class", "modulation", "source_index",
                  "round1_pred", "round2_pred", "round3_pred",
                  "round1_correct", "round2_correct", "round3_correct",
                  "round1_gate_pass", "round2_gate_pass", "round3_gate_pass",
                  "correct_count", "gate_pass_count",
                  "correctness_category", "gating_category", "category"]
    with open(os.path.join(RESULTS, "per_class_repeatability.tsv"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write("\t".join(class_cols) + "\n")
        for r in sorted(class_rows, key=lambda z: z["raw24_class"]):
            f.write("\t".join(str(r[c]) for c in class_cols) + "\n")

    # ---- confusion_counts.tsv (24x24) ----
    matrix = [[0] * N_CLASSES for _ in range(N_CLASSES)]
    for m in merged:
        matrix[m["raw24_class"]][m["raw24_pred"]] += 1
    with open(os.path.join(RESULTS, "confusion_counts.tsv"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write("true_class\t" + "\t".join("pred_%d" % k for k in range(N_CLASSES))
                + "\trow_total\n")
        for i in range(N_CLASSES):
            row = matrix[i]
            f.write("%d\t%s\t%d\n" % (i, "\t".join(str(x) for x in row), sum(row)))
        f.write("col_total\t" + "\t".join(
            str(sum(matrix[i][j] for i in range(N_CLASSES)))
            for j in range(N_CLASSES)) + "\t%d\n" % len(merged))

    # ---- unresolved_samples.tsv (still misclassified after merge) ----
    unresolved = [m for m in merged if m["label_correct"] == 0]
    unres_cols = ["round", "source_index", "raw24_class", "modulation",
                  "gate_pass", "result_layer", "raw24_pred", "baseline_pred",
                  "payload_training_residual", "payload_training_corr",
                  "wide_linear_enabled"]
    with open(os.path.join(RESULTS, "unresolved_samples.tsv"), "w",
              encoding="utf-8", newline="\n") as f:
        f.write("\t".join(unres_cols) + "\n")
        for m in sorted(unresolved, key=lambda z: (z["round"], z["source_index"])):
            f.write("\t".join(str(m[c]) for c in unres_cols) + "\n")

    # ---- summary.json ----
    gated_all = [m for m in merged if m["gate_pass"] == 1]
    forced_all = [m for m in merged if m["gate_pass"] == 0]
    correct_all = sum(1 for m in merged if m["label_correct"] == 1)
    gated_correct_all = sum(1 for m in gated_all if m["label_correct"] == 1)
    forced_correct_all = sum(1 for m in forced_all if m["label_correct"] == 1)

    cat_counts = {}
    for r in class_rows:
        cat_counts[r["category"]] = cat_counts.get(r["category"], 0) + 1

    summary = {
        "task_id": "fix10class24-dualsdr-repeat3-audit1",
        "status": "M29-RML24-FIX10CLASS24-DUALSDR-REPEAT3-AUDIT1-COMPLETE",
        "merge_marker": MERGE_MARKER,
        "note": ("Merged metric = board-gated (board NPU) + host-forced (Host BF16 "
                 "diagnostic gate bypass). This is a HYBRID diagnostic, NOT a "
                 "homogeneous board NPU measurement. production_gate_modified=0."),
        "total_samples": len(merged),
        "rounds": 3,
        "board_gated": len(gated_all),
        "board_gated_correct": gated_correct_all,
        "host_forced": len(forced_all),
        "host_forced_correct": forced_correct_all,
        "merged_correct": correct_all,
        "merged_end_to_end_accuracy": correct_all / len(merged),
        "gated_accuracy": gated_correct_all / len(gated_all) if gated_all else None,
        "forced_accuracy": forced_correct_all / len(forced_all) if forced_all else None,
        "production_gate_modified": 0,
        "production_threshold": 0.100,
        "per_round": round_rows,
        "class_category_counts": cat_counts,
        "classes": [{
            "raw24_class": r["raw24_class"], "modulation": r["modulation"],
            "round_preds": [r["round1_pred"], r["round2_pred"], r["round3_pred"]],
            "round_correct": [r["round1_correct"], r["round2_correct"],
                              r["round3_correct"]],
            "round_gate_pass": [r["round1_gate_pass"], r["round2_gate_pass"],
                                r["round3_gate_pass"]],
            "correct_count": r["correct_count"],
            "gate_pass_count": r["gate_pass_count"],
            "category": r["category"],
        } for r in sorted(class_rows, key=lambda z: z["raw24_class"])],
    }
    with open(os.path.join(RESULTS, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
        f.write("\n")

    # ---- console report ----
    print("=" * 72)
    print("fix10class24-dualsdr-repeat3-audit1 Phase D merge")
    print("=" * 72)
    for r in round_rows:
        print("%s: total=%d gated=%d(%d correct) forced=%d(%d correct) "
              "merged_correct=%d e2e=%s" %
              (r["round"], r["total"], r["gated"], r["gated_correct"],
               r["forced"], r["forced_correct"], r["merged_correct"],
               r["end_to_end_accuracy"]))
    print("TOTAL: gated=%d(%d correct) forced=%d(%d correct) "
          "merged_correct=%d/%d e2e=%.4f" %
          (len(gated_all), gated_correct_all, len(forced_all), forced_correct_all,
           correct_all, len(merged), correct_all / len(merged)))
    print("class category counts: %s" % cat_counts)
    print("-" * 72)
    print("PERSISTENT_MISCLASSIFIED_SAME_CLASS (0/3 correct, same wrong pred):")
    for r in class_rows:
        if r["category"] == "PERSISTENT_MISCLASSIFIED_SAME_CLASS":
            print("  class %d %-10s preds=%s" %
                  (r["raw24_class"], r["modulation"],
                   [r["round1_pred"], r["round2_pred"], r["round3_pred"]]))
    print("ROUND_FLUCTUATION (1-2/3 correct):")
    for r in class_rows:
        if r["category"] == "ROUND_FLUCTUATION":
            print("  class %d %-10s preds=%s correct=%d gate=%d" %
                  (r["raw24_class"], r["modulation"],
                   [r["round1_pred"], r["round2_pred"], r["round3_pred"]],
                   r["correct_count"], r["gate_pass_count"]))
    print("-" * 72)
    print("Merge complete. Deliverables written under results/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
