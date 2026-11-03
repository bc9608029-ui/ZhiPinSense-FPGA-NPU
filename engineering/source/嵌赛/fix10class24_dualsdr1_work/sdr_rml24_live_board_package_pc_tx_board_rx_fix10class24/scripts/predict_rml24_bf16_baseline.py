#!/usr/bin/env python3
"""predict_rml24_bf16_baseline.py -- fix10class24-dualsdr1 §6 (Phase 1).

Run the frozen full-network BF16 24-class iCraft model on the iCraft **Host**
backend (NOT PyTorch) over the 24 fixed clean24_smoke recovered tensors, and emit
the BF16 24-raw-class baseline the board NPU run compares against.

    24 samples, one per class, raw24 (AM-SSB-WC=17 / AM-SSB-SC=18 kept separate,
    NO 24->23 merge).  Prediction == argmax over the 24 raw logits.

Outputs (all in --out-dir):
  * clean24_smoke_raw24_bf16_baseline.tsv   (7-col C++ baseline loader input)
  * clean24_smoke_raw24_bf16_predictions.tsv (per-sample evidence + margins)
  * clean24_smoke_raw24_bf16_report.json
  * clean24_smoke_raw24_bf16_report.md

The baseline TSV columns (contract for board_package/rml24_bf16_baseline.hpp):
    source_index  original_sha256  raw24_class  modulation  split_role
    frozen_bf16_raw24_pred  model_sha256

Hard requirements enforced (any violation -> exit 1):
  * 24/24 predictions correct (pred == raw24_class).
  * 24/24 predictions match the frozen PyTorch raw24 pred (manifest col
    frozen_raw24_pred) -- BF16 Host must reproduce the FP32 argmax on all 24.
  * AM-SSB-WC -> 17 and AM-SSB-SC -> 18 (kept separate, no merge).
  * No NaN/Inf in any of the 24x24 logits.
  * No sample replaced: recovered_tensor SHA re-verified against the manifest.

Runs icraft-run.exe with the Host backend and parses the dumped network output
(``<log_path>/model_24class/ftmpHQB/922.ftmp`` == 24 little-endian fp32 logits,
the output Value v_id 922).  Each sample runs in an isolated temp cwd so the
icraft ``hardopLog/`` side-effect never pollutes the tree.

Pure stdlib + numpy; API machine only (has icraft-run.exe).  Never touches the
board / NPU / RF.

Usage:
    python -I scripts/predict_rml24_bf16_baseline.py \
        --icraft-run D:/icraft/bin/icraft-run.exe \
        --model-dir F:/嵌赛/.../model_rml24_bf16 \
        --manifest F:/嵌赛/fix10class24_prep1_work/clean24_smoke/clean24_smoke_manifest.tsv \
        --tensor-dir F:/嵌赛/fix10class24_prep1_work/clean24_smoke \
        --out-dir F:/嵌赛/.../baselines
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

MANIFEST_HEADER = [
    "sample_index", "source_index", "raw24_class", "deployed23_class",
    "modulation", "snr_db", "split_role", "global_K", "original_dc_i",
    "original_dc_q", "ac_rms", "rec_scale", "complex_count", "sample_rate",
    "tx_rms", "tx_peak", "clip_count", "edge_policy", "guard",
    "original_sha256", "quantized_sha256", "recovered_tensor_sha256",
    "quantized_file", "recovered_tensor_file",
    "tx_scale", "frozen_raw24_pred", "frozen_deployed23_pred",
]

BASELINE_HEADER = ["source_index", "original_sha256", "raw24_class", "modulation",
                   "split_role", "frozen_bf16_raw24_pred", "model_sha256"]
PRED_HEADER = ["source_index", "raw24_class", "frozen_bf16_raw24_pred",
               "frozen_pytorch_raw24_pred", "top1_logit", "top2_logit",
               "margin", "correct_raw24", "match_frozen_pytorch"]

NETWORK_NAME = "model_24class"
EXPECT_CLASS_COUNT = 24
WC_CLASS, SC_CLASS = 17, 18


def fail(msg: str) -> None:
    print("FAIL: %s" % msg, file=sys.stderr)
    sys.exit(1)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def parse_manifest(path: Path) -> list[dict]:
    if not path.is_file():
        fail("manifest not found: %s" % path)
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines:
        fail("manifest empty")
    header = lines[0].rstrip("\n").split("\t")
    if header != MANIFEST_HEADER:
        fail("manifest header not the 27-col clean24 schema (got %d cols)"
             % len(header))
    rows = []
    seen = set()
    for lineno, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        if len(f) != len(MANIFEST_HEADER):
            fail("manifest line %d has %d cols (want %d)"
                 % (lineno, len(f), len(MANIFEST_HEADER)))
        row = dict(zip(MANIFEST_HEADER, f))
        sid = int(row["source_index"])
        if sid in seen:
            fail("duplicate source_index=%d" % sid)
        seen.add(sid)
        rows.append(row)
    return rows


def run_host_infer(icraft_run: Path, model_json: Path, model_raw: Path,
                   input_bin: Path, workdir: Path) -> np.ndarray:
    """Run icraft-run Host backend; return the 24 raw logits as fp32 ndarray."""
    log_path = workdir / "logs"
    cmd = [
        str(icraft_run),
        "--json", str(model_json),
        "--raw", str(model_raw),
        "--network", NETWORK_NAME,
        "--input", str(input_bin),
        "--backends", "Host",
        "--dump_output",
        "--log_path", str(log_path),
    ]
    proc = subprocess.run(cmd, cwd=str(workdir), capture_output=True)
    if proc.returncode != 0:
        fail("icraft-run exit %d: %s" % (proc.returncode,
                                          proc.stderr.decode("utf-8", "replace")[-2000:]))
    ftmp_dir = log_path / NETWORK_NAME / "ftmpHQB"
    ftmps = list(ftmp_dir.glob("*.ftmp")) if ftmp_dir.is_dir() else []
    if len(ftmps) != 1:
        fail("expected exactly 1 ftmp under %s, got %d"
             % (ftmp_dir, len(ftmps)))
    raw = ftmps[0].read_bytes()
    if len(raw) != EXPECT_CLASS_COUNT * 4:
        fail("ftmp %s is %d bytes (want %d)" % (ftmps[0].name, len(raw),
                                                EXPECT_CLASS_COUNT * 4))
    logits = np.frombuffer(raw, dtype="<f4").astype(np.float64)
    return logits


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--icraft-run", default=None)
    ap.add_argument("--model-dir", default=None)
    ap.add_argument("--manifest", default=None)
    ap.add_argument("--tensor-dir", default=None)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)

    if args.self_test:
        return self_test()

    for name in ("icraft_run", "model_dir", "manifest", "tensor_dir", "out_dir"):
        if getattr(args, name) is None:
            ap.error("--%s is required (or use --self-test)" % name.replace("_", "-"))

    icraft_run = Path(args.icraft_run)
    if not icraft_run.is_file():
        fail("icraft-run.exe not found: %s" % icraft_run)
    model_dir = Path(args.model_dir)
    model_json = model_dir / "rml24_adamrv11_bf16.json"
    model_raw = model_dir / "rml24_adamrv11_bf16.raw"
    if not model_json.is_file() or not model_raw.is_file():
        fail("model json/raw not found under %s" % model_dir)

    sums_path = model_dir / "model_SHA256SUMS.txt"
    if not sums_path.is_file():
        fail("model_SHA256SUMS.txt not found")
    recorded = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        parts = line.split()
        if len(parts) == 2:
            recorded[parts[1]] = parts[0]
    model_sha = recorded.get("rml24_adamrv11_bf16.json")
    if not model_sha:
        fail("json SHA not in model_SHA256SUMS.txt")
    if sha256_bytes(model_json.read_bytes()) != model_sha:
        fail("model json SHA does not match model_SHA256SUMS.txt")

    tensor_dir = Path(args.tensor_dir)
    rows = parse_manifest(Path(args.manifest))
    if len(rows) != EXPECT_CLASS_COUNT:
        fail("expected %d samples in manifest, got %d" % (EXPECT_CLASS_COUNT, len(rows)))
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    pred_rows = []
    all_logits = {}
    nan_or_inf = 0
    for r in rows:
        src = int(r["source_index"])
        fname = r["recovered_tensor_file"]
        expect_sha = r["recovered_tensor_sha256"]
        tpath = tensor_dir / fname
        if not tpath.is_file():
            fail("recovered tensor missing: %s" % tpath)
        tb = tpath.read_bytes()
        if len(tb) != 2 * 1024 * 4:
            fail("%s size %dB (want 8192B)" % (fname, len(tb)))
        if sha256_bytes(tb) != expect_sha:
            fail("%s SHA mismatch (sample not replaced: source_index=%d)" % (fname, src))

        with tempfile.TemporaryDirectory(prefix="rml24bf16_") as td:
            workdir = Path(td)
            inp = workdir / "input.bin"
            inp.write_bytes(tb)
            logits = run_host_infer(icraft_run, model_json, model_raw, inp, workdir)

        if not np.all(np.isfinite(logits)):
            nan_or_inf += 1
        argmax = int(np.argmax(logits))
        order = np.argsort(logits)[::-1]
        top1 = float(logits[order[0]])
        top2 = float(logits[order[1]]) if len(order) > 1 else float("nan")
        margin = top1 - top2
        pytorch_pred = int(r["frozen_raw24_pred"])
        raw24_class = int(r["raw24_class"])
        correct = argmax == raw24_class
        match_pytorch = argmax == pytorch_pred
        all_logits[str(src)] = [float(x) for x in logits]
        pred_rows.append({
            "source_index": src,
            "raw24_class": raw24_class,
            "frozen_bf16_raw24_pred": argmax,
            "frozen_pytorch_raw24_pred": pytorch_pred,
            "top1_logit": top1,
            "top2_logit": top2,
            "margin": margin,
            "correct_raw24": correct,
            "match_frozen_pytorch": match_pytorch,
        })
        print("[infer] source_index=%d modulation=%s pred=%d (raw24_class=%d) "
              "top1=%.6f margin=%.6f" % (src, r["modulation"], argmax, raw24_class,
                                        top1, margin))

    # ---- hard requirements ----
    n = len(pred_rows)
    correct = sum(1 for p in pred_rows if p["correct_raw24"])
    match = sum(1 for p in pred_rows if p["match_frozen_pytorch"])
    wc = [p for p in pred_rows if p["raw24_class"] == WC_CLASS]
    sc = [p for p in pred_rows if p["raw24_class"] == SC_CLASS]
    wc_ok = len(wc) == 1 and wc[0]["frozen_bf16_raw24_pred"] == WC_CLASS
    sc_ok = len(sc) == 1 and sc[0]["frozen_bf16_raw24_pred"] == SC_CLASS

    ok = (correct == n and match == n and wc_ok and sc_ok and nan_or_inf == 0
          and len(pred_rows) == EXPECT_CLASS_COUNT)
    if not ok:
        fail("BF16 baseline verification failed: correct=%d/%d match_pytorch=%d/%d "
             "wc_ok=%d sc_ok=%d nan_or_inf=%d" % (correct, n, match, n, wc_ok, sc_ok,
                                                  nan_or_inf))

    # ---- write baseline TSV ----
    baseline_lines = ["\t".join(BASELINE_HEADER)]
    for r, p in zip(rows, pred_rows):
        baseline_lines.append("\t".join([
            str(r["source_index"]), r["original_sha256"], r["raw24_class"],
            r["modulation"], r["split_role"], str(p["frozen_bf16_raw24_pred"]),
            model_sha,
        ]))
    baseline_path = out_dir / "clean24_smoke_raw24_bf16_baseline.tsv"
    baseline_path.write_text("\n".join(baseline_lines) + "\n", encoding="utf-8")

    # ---- write predictions TSV ----
    pred_lines = ["\t".join(PRED_HEADER)]
    for p in pred_rows:
        pred_lines.append("\t".join([
            str(p["source_index"]), str(p["raw24_class"]),
            str(p["frozen_bf16_raw24_pred"]), str(p["frozen_pytorch_raw24_pred"]),
            repr(p["top1_logit"]), repr(p["top2_logit"]), repr(p["margin"]),
            "1" if p["correct_raw24"] else "0",
            "1" if p["match_frozen_pytorch"] else "0",
        ]))
    (out_dir / "clean24_smoke_raw24_bf16_predictions.tsv").write_text(
        "\n".join(pred_lines) + "\n", encoding="utf-8")

    # ---- report ----
    report = {
        "task": "M29-RML24-FIX10CLASS24-BF16-DUALSDR-PHASE1",
        "backend": "icraft-host-bf16",
        "network_name": NETWORK_NAME,
        "model_json_sha256": model_sha,
        "model_raw_sha256": recorded.get("rml24_adamrv11_bf16.raw"),
        "class_count": EXPECT_CLASS_COUNT,
        "deployment_mode": "RAW24_UNMERGED",
        "sample_count": n,
        "correct_raw24": correct,
        "match_frozen_pytorch": match,
        "wc_separate_ok": wc_ok,
        "sc_separate_ok": sc_ok,
        "nan_or_inf": nan_or_inf,
        "verdict": "PASS" if ok else "FAIL",
        "predictions": [{
            "source_index": p["source_index"],
            "raw24_class": p["raw24_class"],
            "frozen_bf16_raw24_pred": p["frozen_bf16_raw24_pred"],
            "frozen_pytorch_raw24_pred": p["frozen_pytorch_raw24_pred"],
            "top1_logit": p["top1_logit"],
            "top2_logit": p["top2_logit"],
            "margin": p["margin"],
            "correct_raw24": p["correct_raw24"],
            "match_frozen_pytorch": p["match_frozen_pytorch"],
            "logits_24": all_logits[str(p["source_index"])],
        } for p in pred_rows],
    }
    (out_dir / "clean24_smoke_raw24_bf16_report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (out_dir / "clean24_smoke_raw24_bf16_report.md").write_text(
        render_markdown(report), encoding="utf-8")

    print("[done] baseline=%s" % baseline_path)
    print("[done] correct=%d/%d match_frozen_pytorch=%d/%d wc=%d sc=%d nan_or_inf=%d"
          % (correct, n, match, n, wc_ok, sc_ok, nan_or_inf))
    return 0


def render_markdown(r: dict) -> str:
    L = []
    L.append("# RML24 BF16 24-class baseline (Phase 1)")
    L.append("")
    L.append("- backend: `%s`" % r["backend"])
    L.append("- network: `%s` (json SHA `%s`, raw SHA `%s`)"
             % (r["network_name"], r["model_json_sha256"], r["model_raw_sha256"]))
    L.append("- deployment mode: `%s`" % r["deployment_mode"])
    L.append("- verdict: **%s**" % r["verdict"])
    L.append("")
    L.append("| metric | value |")
    L.append("|---|---|")
    L.append("| samples | %d |" % r["sample_count"])
    L.append("| correct (pred==raw24_class) | %d/%d |" % (r["correct_raw24"], r["sample_count"]))
    L.append("| match frozen PyTorch | %d/%d |" % (r["match_frozen_pytorch"], r["sample_count"]))
    L.append("| AM-SSB-WC kept separate (17) | %s |" % r["wc_separate_ok"])
    L.append("| AM-SSB-SC kept separate (18) | %s |" % r["sc_separate_ok"])
    L.append("| NaN/Inf logits | %d |" % r["nan_or_inf"])
    L.append("")
    L.append("## Per-sample predictions")
    L.append("")
    L.append("| source_index | raw24 | BF16 pred | PyTorch pred | margin |")
    L.append("|---|---|---|---|---|")
    for p in r["predictions"]:
        L.append("| %d | %d | %d | %d | %.6f |" % (
            p["source_index"], p["raw24_class"], p["frozen_bf16_raw24_pred"],
            p["frozen_pytorch_raw24_pred"], p["margin"]))
    L.append("")
    return "\n".join(L) + "\n"


def self_test() -> int:
    # Non-inference logic: manifest parse + baseline header + argmax on a mock.
    import tempfile
    npass = 0
    with tempfile.TemporaryDirectory() as td:
        p = Path(td)
        # build a minimal valid 27-col manifest (2 rows, WC + SC)
        header = "\t".join(MANIFEST_HEADER)
        def mk(src, cls, mod):
            return "\t".join([
                str(src // 500), str(src), str(cls), str(cls if cls < 17 else 17),
                mod, "nan", "holdout", "2048", "0", "0", "1", "1", "53760", "2560000",
                "893", "2613", "0", "zero", "832",
                "0" * 64, "1" * 64, "2" * 64,
                "clean_x.ci16", "recovered_tensor_x.f32",
                "2.29", str(cls), str(cls if cls < 17 else 17),
            ])
        m = p / "clean24_smoke_manifest.tsv"
        m.write_text(header + "\n" + mk(8500, 17, "AM-SSB-WC") + "\n" + mk(9000, 18, "AM-SSB-SC") + "\n",
                     encoding="utf-8")
        rows = parse_manifest(m)
        if len(rows) == 2 and rows[0]["raw24_class"] == "17":
            npass += 1
            print("  OK  parse_manifest 27-col schema")
        else:
            print("  BAD parse_manifest")
    # argmax sanity (mock logits)
    logits = np.full(24, -5.0); logits[17] = 3.0; logits[18] = 2.9
    if int(np.argmax(logits)) == 17:
        npass += 1
        print("  OK  argmax keeps WC=17 separate")
    else:
        print("  BAD argmax")
    print("self-test: %d/2 correct" % npass)
    return 0 if npass == 2 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
