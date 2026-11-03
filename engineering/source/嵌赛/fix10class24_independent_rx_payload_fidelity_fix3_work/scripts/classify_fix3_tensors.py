#!/usr/bin/env python3
"""classify_fix3_tensors.py -- Fix3 Phase A steps 3-5: independent host re-classification.

Re-runs the FROZEN BF16 24-class model on the iCraft **Host** backend over the 24
recovered tensors (N.recovered.tensor.bin), then compares the host re-derivation
against the board's recorded predictions and logits.  This is the independent
credibility cross-check: does an independent host re-run reproduce the board's
collapse to AM-SSB-WC/SC (19->18, 4->17, 1 reject)?

Because the Host backend runs the same BF16 model with identical quantization,
host logits must match the board's pass1 logits byte-for-byte when the model input
is unchanged -- any mismatch flags a data/transport integrity problem, NOT a model
problem.  We report both argmax agreement and logit-byte agreement separately.

Recomputed (all with the 24-frame denominator intact -- gate rejects are NOT
dropped):
  correct/24, coverage (gated/24), gated accuracy (correct/gated),
  end-to-end accuracy (correct/24), 24x24(+reject) confusion matrix, per-class
  migration (true class -> predicted class).

Outputs (--out-dir):
  inference_crosscheck.tsv   -- per frame: host logits argmax + top1/top2/margin,
                                board_pred, board pass1 argmax, agreement flags
  confusion_matrix.tsv       -- 24 true rows x 25 pred cols (0..23 + reject)
  per_class_metrics.tsv      -- per true-class: n, gated, correct, migration

Usage:
    python -I scripts/classify_fix3_tensors.py \
        --capture-dir F:/嵌赛/board_capture/rml24_fix2_dual_1773374951_244 \
        --model-dir  F:/嵌赛/.../model_rml24_bf16 \
        --icraft-run D:/icraft/bin/icraft-run.exe \
        --out-dir results
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

# Allow `python -I` (isolated mode, no script dir on sys.path) to still import
# the sibling fix3_common module from this same scripts/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fix3_common as c


def run_host_infer(icraft_run: Path, model_json: Path, model_raw: Path,
                   input_bin: Path, workdir: Path) -> np.ndarray:
    """Run icraft-run Host backend; return the 24 raw logits as fp32 ndarray."""
    log_path = workdir / "logs"
    cmd = [
        str(icraft_run),
        "--json", str(model_json),
        "--raw", str(model_raw),
        "--network", c.NETWORK_NAME,
        "--input", str(input_bin),
        "--backends", "Host",
        "--dump_output",
        "--log_path", str(log_path),
    ]
    proc = subprocess.run(cmd, cwd=str(workdir), capture_output=True)
    if proc.returncode != 0:
        c.fail("icraft-run exit %d: %s"
               % (proc.returncode, proc.stderr.decode("utf-8", "replace")[-2000:]))
    ftmp_dir = log_path / c.NETWORK_NAME / "ftmpHQB"
    ftmps = list(ftmp_dir.glob("*.ftmp")) if ftmp_dir.is_dir() else []
    if len(ftmps) != 1:
        c.fail("expected exactly 1 ftmp under %s, got %d" % (ftmp_dir, len(ftmps)))
    raw = ftmps[0].read_bytes()
    if len(raw) != c.EXPECT_CLASS_COUNT * 4:
        c.fail("ftmp %s is %d bytes (want %d)" % (ftmps[0].name, len(raw),
                                                  c.EXPECT_CLASS_COUNT * 4))
    return np.frombuffer(raw, dtype="<f4").astype(np.float64)


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture-dir", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--icraft-run", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--no-infer", action="store_true",
                    help="skip icraft-run (re-derive board argmax only, for offline dry-run)")
    args = ap.parse_args(argv)

    capture_dir = Path(args.capture_dir)
    model_dir = Path(args.model_dir)
    icraft_run = Path(args.icraft_run)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    model_json = model_dir / "rml24_adamrv11_bf16.json"
    model_raw = model_dir / "rml24_adamrv11_bf16.raw"
    if not model_json.is_file() or not model_raw.is_file():
        c.fail("model json/raw missing under %s" % model_dir)
    if c.sha256_file(model_json) != c.FROZEN_MODEL_JSON_SHA256:
        c.fail("model json SHA mismatch (not the frozen BF16 model)")
    if c.sha256_file(model_raw) != c.FROZEN_MODEL_RAW_SHA256:
        c.fail("model raw SHA mismatch (not the frozen BF16 model)")

    results = c.load_results_tsv(capture_dir / "board_independent_rx_results.tsv")

    xrows = []
    n_host_ran = 0
    n_argmax_agree = 0
    n_logit_byte_agree = 0
    n_correct_host = 0

    for r in results:
        sid = int(r["source_index"])
        cls = int(r["class_index"])
        board_pred = int(r["board_pred"])

        # board pass1 argmax (from the persisted logits TSV, NOT from board_pred --
        # independent re-derivation of the argmax from the recorded 24 logits).
        logits = c.parse_logits_tsv(capture_dir / ("%d.logits.tsv" % sid))
        board_pass1 = logits["pass1"]
        board_pass1_argmax = int(np.argmax(board_pass1)) if board_pass1 else -1

        ten_path = capture_dir / ("%d.recovered.tensor.bin" % sid)
        tb = ten_path.read_bytes()
        if c.sha256_bytes(tb) != r["model_input_sha256"]:
            c.fail("frame %d tensor SHA mismatch before inference" % sid)

        host_logits = None
        host_argmax = -1
        if args.no_infer:
            host_logits = None
            host_argmax = board_pass1_argmax  # dry-run: assume board == host
        elif board_pred >= 0 and board_pass1:  # gated + classified frames only
            with tempfile.TemporaryDirectory(prefix="fix3cls_") as td:
                wd = Path(td)
                inp = wd / "input.bin"
                inp.write_bytes(tb)
                host_logits = run_host_infer(icraft_run, model_json, model_raw, inp, wd)
            n_host_ran += 1
            host_argmax = int(np.argmax(host_logits))

        # agreement
        argmax_agree = (host_argmax == board_pred) if host_logits is not None else None
        logit_byte_agree = None
        if host_logits is not None and board_pass1:
            logit_byte_agree = bool(np.array_equal(
                host_logits.astype(np.float32),
                np.asarray(board_pass1, dtype=np.float32)))

        if host_argmax >= 0:
            if host_argmax == cls:
                n_correct_host += 1
        if argmax_agree:
            n_argmax_agree += 1
        if logit_byte_agree:
            n_logit_byte_agree += 1

        # top1/top2/margin from host (or board fallback)
        if host_logits is not None:
            order = np.argsort(host_logits)[::-1]
            top1 = float(host_logits[order[0]])
            top2 = float(host_logits[order[1]])
            margin = top1 - top2
            top2_cls = int(order[1])
        elif board_pass1:
            a = np.asarray(board_pass1, dtype=np.float64)
            order = np.argsort(a)[::-1]
            top1 = float(a[order[0]])
            top2 = float(a[order[1]])
            margin = top1 - top2
            top2_cls = int(order[1])
        else:
            top1 = top2 = margin = float("nan")
            top2_cls = -1

        xrows.append({
            "source_index": sid, "class_index": cls, "class_name": r["class_name"],
            "gated": int(r["gated"]), "board_pred": board_pred,
            "board_pass1_argmax": board_pass1_argmax,
            "host_argmax": host_argmax,
            "host_ran": 1 if host_logits is not None else 0,
            "argmax_agree": argmax_agree if argmax_agree is not None else "",
            "logit_byte_agree": logit_byte_agree if logit_byte_agree is not None else "",
            "top1_logit": top1, "top2_logit": top2, "top2_class": top2_cls,
            "margin": margin,
            "host_correct": int(host_argmax == cls) if host_argmax >= 0 else 0,
        })

    # ---- write inference_crosscheck.tsv ----
    hdr = ["source_index", "class_index", "class_name", "gated", "board_pred",
           "board_pass1_argmax", "host_argmax", "host_ran", "argmax_agree",
           "logit_byte_agree", "top1_logit", "top2_logit", "top2_class", "margin",
           "host_correct"]
    rows = [[x["source_index"], x["class_index"], x["class_name"], x["gated"],
             x["board_pred"], x["board_pass1_argmax"], x["host_argmax"], x["host_ran"],
             x["argmax_agree"], x["logit_byte_agree"],
             ("%.6f" % x["top1_logit"]), ("%.6f" % x["top2_logit"]),
             x["top2_class"], ("%.6f" % x["margin"]), x["host_correct"]] for x in xrows]
    c.write_tsv(out_dir / "inference_crosscheck.tsv", hdr, rows)

    # ---- confusion matrix (true class x predicted, 0..23 + reject=col 24) ----
    n = len(xrows)
    cm = np.zeros((24, 25), dtype=int)
    for x in xrows:
        pred_col = x["host_argmax"] if x["host_argmax"] >= 0 else 24
        cm[x["class_index"], pred_col] += 1

    cm_header = ["true_class", "true_name"] + [str(i) for i in range(24)] + ["reject"]
    cm_rows = []
    for i in range(24):
        cm_rows.append([i, c.LABELS[i]] + [int(cm[i, j]) for j in range(25)])
    c.write_tsv(out_dir / "confusion_matrix.tsv", cm_header, cm_rows)

    # ---- per-class metrics + migration ----
    pm_header = ["class_index", "class_name", "n", "gated", "classified",
                 "correct", "pred_class", "pred_name", "migrated_to"]
    pm_rows = []
    for i in range(24):
        sub = [x for x in xrows if x["class_index"] == i]
        n_i = len(sub)
        gated_i = sum(1 for x in sub if x["gated"])
        class_i = sum(1 for x in sub if x["host_argmax"] >= 0)
        corr_i = sum(1 for x in sub if x["host_correct"])
        # migration: for the (single) sample of this class, where did it go?
        pred_i = sub[0]["host_argmax"] if sub else -1
        pred_name = c.LABELS[pred_i] if 0 <= pred_i < 24 else ("reject" if pred_i == -1 else "?")
        migrated = (pred_i != i)
        pm_rows.append([i, c.LABELS[i], n_i, gated_i, class_i, corr_i,
                        pred_i, pred_name, int(migrated)])
    c.write_tsv(out_dir / "per_class_metrics.tsv", pm_header, pm_rows)

    # ---- aggregate ----
    correct = n_correct_host
    gated = sum(1 for x in xrows if x["gated"])
    classified = sum(1 for x in xrows if x["host_argmax"] >= 0)
    coverage = gated / n if n else 0.0
    gated_acc = correct / gated if gated else 0.0
    e2e_acc = correct / n if n else 0.0
    n_host = n_host_ran

    summary = {
        "frame_count": n,
        "gated": gated,
        "gate_reject": n - gated,
        "classified": classified,
        "correct": correct,
        "coverage": coverage,
        "gated_accuracy": gated_acc,
        "end_to_end_accuracy": e2e_acc,
        "host_inferences_run": n_host,
        "argmax_agree": n_argmax_agree,
        "logit_byte_agree": n_logit_byte_agree,
    }
    c.dumps_json(summary, out_dir / "summary.json")

    print("[crosscheck] host_infer=%d argmax_agree=%d logit_byte_agree=%d"
          % (n_host, n_argmax_agree, n_logit_byte_agree))
    print("[crosscheck] gated=%d reject=%d classified=%d correct=%d"
          % (gated, n - gated, classified, correct))
    print("[crosscheck] coverage=%.4f gated_acc=%.4f e2e_acc=%.4f"
          % (coverage, gated_acc, e2e_acc))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
