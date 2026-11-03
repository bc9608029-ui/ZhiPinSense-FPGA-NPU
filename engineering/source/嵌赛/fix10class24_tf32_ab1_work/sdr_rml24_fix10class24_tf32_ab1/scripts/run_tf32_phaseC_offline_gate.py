#!/usr/bin/env python3
"""run_tf32_phaseC_offline_gate.py -- Phase C offline hard-gate: TF32 vs BF16.

Runs the SAME archived real-RF model_input tensors through (a) the current
production BF16 network and (b) the new pure-TF32 network on the iCraft Host
backend, then compares raw24 argmax + logits.  This is the decisive go/no-go
measurement: does TF32 change any real-RF prediction, and do changes move
toward the true class?

Inputs (auto-discovered; true class = source_index // 500, raw24 frozen order):
  C2 single-SDR  --scalarwl-dir   <dir>/<source_index>/model_input_{scalar,wl}_f32le.bin
  C2 single-SDR  --fourway-dir    <dir>/model_input_{scalar,wl}_f32le.bin (OQPSK 11500)
  C3 dual-SDR    --full24-dir     <dir>/<source_index>/model_input_f32le.bin

Every forward is >=2x and byte-identity checked.  Outputs:
  results/tf32_phaseC/{per_sample.tsv, comparison_summary.json, comparison_report.md}

Pure stdlib + icraft-run Host.  API-only: never touches board/NPU.  Uses the
space-free icraft copy (Host backend fails on the "CLI v3.39.0" space path).

  python -I scripts/run_tf32_phaseC_offline_gate.py \
      --icraft-run D:/icraft/bin/icraft-run.exe \
      --bf16-model-dir F:/嵌赛/fix10class24_scalarwl_4way_work/sdr_rml24_fix10class24_scalarwl_4way/model_rml24_bf16 \
      --tf32-model-dir model_rml24_tf32 \
      --scalarwl-dir F:/嵌赛/board_capture/scalarwl_mixed24/scalarwl_mixed24_1773376147 \
      --fourway-dir F:/嵌赛/board_capture/scalarwl_4way/scalarwl_out_fix1_1773374345 \
      --full24-dir F:/嵌赛/fix10class24_rxresidual_audit1_work/sdr_rml24_fix10class24_rxresidual_audit1/results/full24_failed_rx_forceclass/forced_classify_export/rml24_full24_failed_rx_1773374413
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import struct
import subprocess
import sys
from pathlib import Path

# frozen raw24 label order (== rml24_raw_contract.SOURCE_LABEL_ORDER_24, DEPLOYED==SOURCE)
LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
    "FM", "GMSK", "OQPSK",
)
NETWORK_NAME = "model_24class"
N_CLASS = 24
N_INPUT_FLOATS = 2 * 1024


def fail(msg: str) -> None:
    print("FAIL: %s" % msg, file=sys.stderr)
    sys.exit(1)


def run_host_infer(icraft_run: Path, model_json: Path, model_raw: Path,
                   input_bin: Path, log_path: Path) -> bytes:
    if log_path.exists():
        shutil.rmtree(log_path)
    log_path.mkdir(parents=True)
    cmd = [str(icraft_run), "--json", str(model_json), "--raw", str(model_raw),
           "--network", NETWORK_NAME, "--input", str(input_bin),
           "--backends", "Host", "--dump_output", "--log_path", str(log_path)]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        fail("icraft-run exit %d\n%s" % (proc.returncode,
                                          proc.stderr.decode("utf-8", "replace")[-2000:]))
    ftmp_dir = log_path / NETWORK_NAME / "ftmpHQB"
    ftmps = list(ftmp_dir.glob("*.ftmp")) if ftmp_dir.is_dir() else []
    if len(ftmps) != 1:
        fail("expected 1 ftmp under %s, got %d" % (ftmp_dir, len(ftmps)))
    raw = ftmps[0].read_bytes()
    if len(raw) != N_CLASS * 4:
        fail("ftmp %d bytes (want %d)" % (len(raw), N_CLASS * 4))
    return raw


def infer_twice(icraft_run: Path, model_json: Path, model_raw: Path,
                input_bin: Path, workdir: Path, tag: str) -> tuple:
    raws = []
    for k in range(2):
        raw = run_host_infer(icraft_run, model_json, model_raw, input_bin,
                             workdir / ("%s_logs%d" % (tag, k + 1)))
        raws.append(raw)
    if raws[0] != raws[1]:
        fail("forward non-deterministic for %s" % input_bin)
    logits = struct.unpack("<%df" % N_CLASS, raws[0])
    if not all(math.isfinite(x) for x in logits):
        fail("non-finite logits for %s" % input_bin)
    argmax = max(range(N_CLASS), key=lambda i: logits[i])
    return logits, argmax


def discover_tensors(args) -> list:
    """Return list of (sample_id, source_index, kind, input_bin)."""
    out = []
    if args.scalarwl_dir:
        d = Path(args.scalarwl_dir)
        if not d.is_dir():
            fail("--scalarwl-dir not a dir: %s" % d)
        for sub in sorted(d.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else 1 << 30):
            if not sub.is_dir() or not sub.name.isdigit():
                continue
            si = int(sub.name)
            for kind, fn in (("scalar", "model_input_scalar_f32le.bin"),
                             ("wl", "model_input_wl_f32le.bin")):
                p = sub / fn
                if p.is_file():
                    out.append(("single-sdr_%s_%s" % (kind, si), si, kind, p))
    if args.fourway_dir:
        d = Path(args.fourway_dir)
        if not d.is_dir():
            fail("--fourway-dir not a dir: %s" % d)
        for kind, fn in (("scalar", "model_input_scalar_f32le.bin"),
                         ("wl", "model_input_wl_f32le.bin")):
            p = d / fn
            if p.is_file():
                out.append(("single-sdr-oqpsk_%s" % kind, 11500, kind, p))
    if args.full24_dir:
        d = Path(args.full24_dir)
        if not d.is_dir():
            fail("--full24-dir not a dir: %s" % d)
        for sub in sorted(d.iterdir(), key=lambda p: int(p.name) if p.name.isdigit() else 1 << 30):
            if not sub.is_dir() or not sub.name.isdigit():
                continue
            si = int(sub.name)
            p = sub / "model_input_f32le.bin"
            if p.is_file():
                out.append(("dual-sdr_%s" % si, si, "wl", p))
    return out


def main(argv) -> int:
    ap = argparse.ArgumentParser(description="TF32 vs BF16 offline hard-gate")
    ap.add_argument("--icraft-run", default="D:/icraft/bin/icraft-run.exe")
    ap.add_argument("--bf16-model-dir", required=True)
    ap.add_argument("--tf32-model-dir", default="model_rml24_tf32")
    ap.add_argument("--scalarwl-dir", default=None)
    ap.add_argument("--fourway-dir", default=None)
    ap.add_argument("--full24-dir", default=None)
    ap.add_argument("--out-dir", default="results/tf32_phaseC")
    ap.add_argument("--workdir", default="phaseC_work")
    args = ap.parse_args(argv)

    icraft_run = Path(args.icraft_run)
    if not icraft_run.is_file():
        fail("icraft-run.exe not found: %s" % icraft_run)
    bf16_dir = Path(args.bf16_model_dir)
    bf16_json, bf16_raw = bf16_dir / "rml24_adamrv11_bf16.json", bf16_dir / "rml24_adamrv11_bf16.raw"
    tf32_dir = Path(args.tf32_model_dir)
    tf32_json, tf32_raw = tf32_dir / "rml24_adamrv11_tf32.json", tf32_dir / "rml24_adamrv11_tf32.raw"
    for p, lbl in ((bf16_json, "bf16 json"), (bf16_raw, "bf16 raw"),
                   (tf32_json, "tf32 json"), (tf32_raw, "tf32 raw")):
        if not p.is_file():
            fail("missing %s: %s" % (lbl, p))

    print("[phaseC] bf16_model_json_sha=%s" % hashlib.sha256(bf16_json.read_bytes()).hexdigest())
    print("[phaseC] bf16_model_raw_sha =%s" % hashlib.sha256(bf16_raw.read_bytes()).hexdigest())
    print("[phaseC] tf32_model_json_sha=%s" % hashlib.sha256(tf32_json.read_bytes()).hexdigest())
    print("[phaseC] tf32_model_raw_sha =%s" % hashlib.sha256(tf32_raw.read_bytes()).hexdigest())

    tensors = discover_tensors(args)
    if not tensors:
        fail("no input tensors discovered (pass --scalarwl-dir/--fourway-dir/--full24-dir)")

    out_dir = Path(args.out_dir)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)
    workdir = Path(args.workdir)
    if workdir.exists():
        shutil.rmtree(workdir)
    workdir.mkdir(parents=True)

    rows = []
    for idx, (sid, si, kind, binp) in enumerate(tensors):
        if binp.stat().st_size != N_INPUT_FLOATS * 4:
            fail("tensor %s size %d != %d" % (binp, binp.stat().st_size, N_INPUT_FLOATS * 4))
        true_class = si // 500
        if true_class < 0 or true_class >= N_CLASS:
            fail("source_index %d -> bad class %d" % (si, true_class))
        tag = "s%03d" % idx
        bf16_logits, bf16_arg = infer_twice(icraft_run, bf16_json, bf16_raw, binp, workdir, tag + "b")
        tf32_logits, tf32_arg = infer_twice(icraft_run, tf32_json, tf32_raw, binp, workdir, tag + "t")
        rows.append({
            "sample_id": sid, "source_index": si, "kind": kind,
            "true_class": true_class, "true_label": LABEL_ORDER_24[true_class],
            "bf16_pred": bf16_arg, "bf16_label": LABEL_ORDER_24[bf16_arg],
            "tf32_pred": tf32_arg, "tf32_label": LABEL_ORDER_24[tf32_arg],
            "bf16_correct": bf16_arg == true_class,
            "tf32_correct": tf32_arg == true_class,
            "argmax_disagree": bf16_arg != tf32_arg,
            "bf16_top_logit": bf16_logits[bf16_arg],
            "tf32_top_logit": tf32_logits[tf32_arg],
            "bf16_true_logit": bf16_logits[true_class],
            "tf32_true_logit": tf32_logits[true_class],
            "max_logit_delta": max(abs(b - t) for b, t in zip(bf16_logits, tf32_logits)),
        })
        print("[phaseC] %-28s src=%5d true=%2d(%s) bf16=%2d(%s)%s tf32=%2d(%s)%s"
              % (sid, si, true_class, LABEL_ORDER_24[true_class],
                 bf16_arg, LABEL_ORDER_24[bf16_arg], "" if bf16_arg == true_class else " X",
                 tf32_arg, LABEL_ORDER_24[tf32_arg], "" if tf32_arg == true_class else " X"))

    # ---- summary ----
    n = len(rows)
    bf16_correct = sum(r["bf16_correct"] for r in rows)
    tf32_correct = sum(r["tf32_correct"] for r in rows)
    disagreements = [r for r in rows if r["argmax_disagree"]]
    to_correct = [r for r in disagreements if r["tf32_correct"] and not r["bf16_correct"]]
    to_wrong = [r for r in disagreements if not r["tf32_correct"] and r["bf16_correct"]]
    both_wrong_flip = [r for r in disagreements if not r["tf32_correct"] and not r["bf16_correct"]]

    summary = {
        "n_samples": n,
        "bf16_correct": bf16_correct,
        "tf32_correct": tf32_correct,
        "bf16_accuracy": round(bf16_correct / n, 6),
        "tf32_accuracy": round(tf32_correct / n, 6),
        "argmax_disagreements": len(disagreements),
        "flip_wrong_to_correct": len(to_correct),
        "flip_correct_to_wrong": len(to_wrong),
        "flip_both_wrong": len(both_wrong_flip),
        "verdict": None,
    }
    if len(disagreements) == 0:
        summary["verdict"] = "TF32_ARGMAX_IDENTICAL_TO_BF16"
    elif len(to_correct) > 0 and len(to_wrong) == 0:
        summary["verdict"] = "TF32_IMPROVES"
    elif len(to_wrong) > 0 and len(to_correct) == 0:
        summary["verdict"] = "TF32_REGRESSES"
    else:
        summary["verdict"] = "TF32_MIXED_CHANGES"

    (out_dir / "comparison_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # per-sample TSV
    header = ["sample_id", "source_index", "kind", "true_class", "true_label",
              "bf16_pred", "bf16_label", "bf16_correct", "tf32_pred", "tf32_label",
              "tf32_correct", "argmax_disagree", "bf16_top_logit", "tf32_top_logit",
              "bf16_true_logit", "tf32_true_logit", "max_logit_delta"]
    with open(out_dir / "per_sample.tsv", "w", encoding="utf-8") as fh:
        fh.write("\t".join(header) + "\n")
        for r in rows:
            fh.write("\t".join(str(r[h]) for h in header) + "\n")

    (out_dir / "comparison_report.md").write_text(render_report(summary, rows), encoding="utf-8")

    print("[phaseC] n=%d  bf16_correct=%d  tf32_correct=%d  disagreements=%d  verdict=%s"
          % (n, bf16_correct, tf32_correct, len(disagreements), summary["verdict"]))
    print("[phaseC] wrote %s" % out_dir)
    return 0


def render_report(s: dict, rows: list) -> str:
    L = ["# TF32 vs BF16 offline hard-gate (Phase C)", ""]
    L.append("| metric | value |")
    L.append("|---|---|")
    for k in ("n_samples", "bf16_correct", "tf32_correct", "bf16_accuracy",
              "tf32_accuracy", "argmax_disagreements", "flip_wrong_to_correct",
              "flip_correct_to_wrong", "flip_both_wrong", "verdict"):
        L.append("| %s | %s |" % (k, s[k]))
    L.append("")
    if s["argmax_disagreements"]:
        L.append("## Argmax disagreements")
        L.append("")
        L.append("| sample | true | bf16 | tf32 | direction |")
        L.append("|---|---|---|---|---|")
        for r in rows:
            if r["argmax_disagree"]:
                if r["tf32_correct"] and not r["bf16_correct"]:
                    d = "wrong->correct"
                elif not r["tf32_correct"] and r["bf16_correct"]:
                    d = "correct->wrong"
                else:
                    d = "both-wrong"
                L.append("| %s | %s | %s | %s | %s |" % (
                    r["sample_id"], r["true_label"], r["bf16_label"], r["tf32_label"], d))
        L.append("")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
