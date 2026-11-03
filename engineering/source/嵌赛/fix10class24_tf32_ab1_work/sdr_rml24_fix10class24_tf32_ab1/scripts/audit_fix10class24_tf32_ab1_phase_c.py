#!/usr/bin/env python3
"""audit_fix10class24_tf32_ab1_phase_c.py -- tf32-ab1 Phase C offline hard-gate.

Runs the TF32 network (model_rml24_tf32) on the SAME inputs already classified
by BF16 / mixed / FP32, and compares argmax against those existing results, so
Phase D (Go/No-Go) can decide whether TF32 changes -- let alone improves --
real-RF 24-class accuracy.

Three input sets (each optional via --phase c1|c2|c3|all):
  C1  clean24_smoke 24 recovered tensors      (compare vs BF16 baseline TSV)
  C2  single-SDR scalarwl 24 x {scalar,wl}    (compare vs logits_*_bf16/mixed.bin)
  C3  dual-SDR full24 rejected captures       (compare vs per_sample_results + raw24_logits)

Fail-closed: TF32 model identity (json/raw SHA), input byte size (8192 f32le),
and finite/24-dim logits are checked.  Never touches board/NPU; uses icraft-run
Host backend via the space-free D:/icraft copy.

  python -I scripts/audit_fix10class24_tf32_ab1_phase_c.py \
      --phase all --icraft-run D:/icraft/bin/icraft-run.exe
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

NETWORK_NAME = "model_24class"
N_CLASS = 24
TF32_JSON_SHA = "8d00a1c31835611f18064389e5b9ecab755afefa5bacd78a983119757e65fa37"
TF32_RAW_SHA = "f8366a109576ea53c9b3ddfd2e7b690590515ff3dfb33c6af7cf6ccafcdb392e"
BF16_JSON_SHA = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"

SOURCE_LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
    "FM", "GMSK", "OQPSK",
)

DEFAULTS = {
    "clean24_dir": "F:/嵌赛/fix10class24_scalarwl_4way_work/sdr_rml24_fix10class24_scalarwl_4way/clean24_smoke",
    "clean24_bf16_baseline": "F:/嵌赛/fix10class24_scalarwl_4way_work/sdr_rml24_fix10class24_scalarwl_4way/baselines/clean24_smoke_raw24_bf16_baseline.tsv",
    "scalarwl_dir": "F:/嵌赛/board_capture/scalarwl_mixed24/scalarwl_mixed24_1773376147",
    "dualsdr_results": "F:/嵌赛/fix10class24_full24_accuracy1_work/sdr_rml24_fix10class24_full24_accuracy1/results/full24_accuracy1",
}


def fail(msg: str) -> None:
    print("FAIL: %s" % msg, file=sys.stderr)
    sys.exit(1)


def read_logits_bin(path: Path) -> list[float]:
    raw = path.read_bytes()
    if len(raw) != N_CLASS * 4:
        fail("%s is %d bytes (want 96)" % (path, len(raw)))
    return list(struct.unpack("<%df" % N_CLASS, raw))


def read_logits_tsv_cell(row: dict) -> list[float]:
    return [float(row["logit_%02d" % i]) for i in range(N_CLASS)]


def argmax(logits) -> int:
    return max(range(N_CLASS), key=lambda i: logits[i])


def run_host_infer(icraft_run: Path, model_json: Path, model_raw: Path,
                   input_bin: Path, log_path: Path) -> list[float]:
    if log_path.exists():
        shutil.rmtree(log_path)
    log_path.mkdir(parents=True)
    cmd = [str(icraft_run), "--json", str(model_json), "--raw", str(model_raw),
           "--network", NETWORK_NAME, "--input", str(input_bin),
           "--backends", "Host", "--dump_output", "--log_path", str(log_path)]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        fail("icraft-run exit %d (input %s): %s"
             % (proc.returncode, input_bin.name,
                proc.stderr.decode("utf-8", "replace")[-1500:]))
    ftmp_dir = log_path / NETWORK_NAME / "ftmpHQB"
    ftmps = list(ftmp_dir.glob("*.ftmp")) if ftmp_dir.is_dir() else []
    if len(ftmps) != 1:
        fail("expected 1 ftmp under %s, got %d" % (ftmp_dir, len(ftmps)))
    raw = ftmps[0].read_bytes()
    if len(raw) != N_CLASS * 4:
        fail("ftmp %d bytes (want %d)" % (len(raw), N_CLASS * 4))
    return list(struct.unpack("<%df" % N_CLASS, raw))


def verify_input(input_bin: Path) -> None:
    if not input_bin.is_file():
        fail("input missing: %s" % input_bin)
    if input_bin.stat().st_size != 2 * 1024 * 4:
        fail("input %s size %d != 8192 (fp32 [2,1024])"
             % (input_bin.name, input_bin.stat().st_size))


def run_tf32(icraft_run, model_json, model_raw, input_bin, workdir, tag):
    verify_input(input_bin)
    # icraft-run's Host backend keys input handling off the file extension:
    # `.f32` is misread as an image (Image2Tensor "out_shape.size()==4"), while
    # `.bin` is treated as a raw [1,2,1024] fp32 tensor.  Stage every input as
    # a `.bin` copy so all three input sets (C1 .f32 / C2 .bin / C3 .bin) take
    # the same, correct path.
    staged = workdir / ("in_%s.bin" % tag)
    staged.write_bytes(input_bin.read_bytes())
    logits = run_host_infer(icraft_run, model_json, model_raw, staged,
                            workdir / ("logs_" + tag))
    if not all(math.isfinite(x) for x in logits):
        fail("non-finite TF32 logits for %s" % tag)
    return logits


def phase_c1(args, model_json, model_raw, workdir, out):
    clean = Path(args.clean24_dir)
    base_rows = []
    seen = set()
    for line in Path(args.clean24_bf16_baseline).read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        r = {"source_index": int(f[0]), "raw24_class": int(f[2]),
             "modulation": f[3], "bf16_pred": int(f[5])}
        seen.add(r["source_index"])
        base_rows.append(r)
    if len(base_rows) != N_CLASS:
        fail("C1: bf16 baseline has %d rows (want 24)" % len(base_rows))

    results = []
    for r in base_rows:
        mod = r["modulation"].lower().replace("-", "_")
        # recovered_tensor file is named by modulation with dashes->underscores
        tensor = clean / ("recovered_tensor_%s.f32" % r["modulation"].lower())
        if not tensor.is_file():
            # fallback: manifest maps modulation to file; use a scan by suffix
            cands = list(clean.glob("recovered_tensor_*%s*.f32" % r["modulation"].lower().replace("-", "_")))
            if not cands:
                fail("C1: tensor for %s not found" % r["modulation"])
            tensor = cands[0]
        logits = run_tf32(args.icraft_run, model_json, model_raw, tensor,
                          workdir, "c1_%d" % r["source_index"])
        pred = argmax(logits)
        results.append({
            "source_index": r["source_index"], "raw24_class": r["raw24_class"],
            "modulation": r["modulation"],
            "tf32_pred": pred, "bf16_pred": r["bf16_pred"],
            "tf32_correct": 1 if pred == r["raw24_class"] else 0,
            "tf32_bf16_agree": 1 if pred == r["bf16_pred"] else 0,
        })
    correct = sum(x["tf32_correct"] for x in results)
    agree = sum(x["tf32_bf16_agree"] for x in results)
    print("[C1 clean24_smoke] tf32_correct=%d/24  tf32_vs_bf16_argmax_agree=%d/24"
          % (correct, agree))
    return {"phase": "c1", "tf32_correct": correct, "total": N_CLASS,
            "tf32_bf16_agree": agree, "rows": results}


def phase_c2(args, model_json, model_raw, workdir, out):
    root = Path(args.scalarwl_dir)
    idxs = sorted(int(p.name) for p in root.iterdir() if p.is_dir() and p.name.isdigit())
    if len(idxs) != N_CLASS:
        fail("C2: scalarwl dir has %d source_index subdirs (want 24)" % len(idxs))
    results = []
    for idx in idxs:
        d = root / str(idx)
        cls = idx // 500
        label = SOURCE_LABEL_ORDER_24[cls]
        rec = {"source_index": idx, "source_class": cls, "modulation": label}
        # existing BF16 / mixed logits (scalar + wl)
        for variant in ("scalar", "wl"):
            bf16 = read_logits_bin(d / ("logits_%s_bf16.bin" % variant))
            mixed = read_logits_bin(d / ("logits_%s_mixed.bin" % variant))
            inp = d / ("model_input_%s_f32le.bin" % variant)
            logits = run_tf32(args.icraft_run, model_json, model_raw, inp,
                              workdir, "c2_%d_%s" % (idx, variant))
            pred = argmax(logits)
            bf16_p = argmax(bf16)
            mixed_p = argmax(mixed)
            rec["%s_tf32_pred" % variant] = pred
            rec["%s_tf32_correct" % variant] = 1 if pred == cls else 0
            rec["%s_bf16_pred" % variant] = bf16_p
            rec["%s_mixed_pred" % variant] = mixed_p
            rec["%s_tf32_diff_bf16" % variant] = 1 if pred != bf16_p else 0
            # numeric evidence: TF32 is genuinely higher-precision (logits differ
            # from BF16) yet argmax is unchanged
            rec["%s_tf32_bf16_max_logit_delta" % variant] = \
                max(abs(a - b) for a, b in zip(logits, bf16))
        results.append(rec)
    # WL is the primary variant per task spec
    wl_correct = sum(r["wl_tf32_correct"] for r in results)
    wl_diff = sum(r["wl_tf32_diff_bf16"] for r in results)
    scalar_diff = sum(r["scalar_tf32_diff_bf16"] for r in results)
    wl_max_delta = max(r["wl_tf32_bf16_max_logit_delta"] for r in results)
    scalar_max_delta = max(r["scalar_tf32_bf16_max_logit_delta"] for r in results)
    print("[C2 scalarwl] tf32_wl_correct=%d/24  tf32_vs_bf16_argmax_diff: wl=%d scalar=%d  "
          "max|tf32-bf16| logit delta: wl=%.4f scalar=%.4f"
          % (wl_correct, wl_diff, scalar_diff, wl_max_delta, scalar_max_delta))
    return {"phase": "c2", "tf32_wl_correct": wl_correct, "total": N_CLASS,
            "wl_tf32_diff_bf16": wl_diff, "scalar_tf32_diff_bf16": scalar_diff,
            "wl_max_logit_delta": wl_max_delta, "scalar_max_logit_delta": scalar_max_delta,
            "rows": results}


def phase_c3(args, model_json, model_raw, workdir, out):
    res = Path(args.dualsdr_results)
    ps = {}
    for line in (res / "per_sample_results.tsv").read_text(encoding="utf-8").splitlines()[1:]:
        if not line.strip():
            continue
        f = line.rstrip("\n").split("\t")
        r = {"source_index": int(f[0]), "source_class": int(f[1]),
             "modulation": f[2], "gated": int(f[4]), "rf_verdict": f[5],
             "forced_raw24_pred": int(f[15]), "forced_label_correct": int(f[16])}
        ps[r["source_index"]] = r
    if len(ps) != N_CLASS:
        fail("C3: per_sample_results has %d rows (want 24)" % len(ps))

    exp = res / "forced_classify_export" / "rml24_full24_accuracy1_1773372865"
    results = []
    n_run = 0
    for idx in sorted(ps):
        r = ps[idx]
        inp = exp / str(idx) / "model_input_f32le.bin"
        if not inp.is_file():
            # gated samples may not have a forced export; skip TF32 (board-only)
            results.append(dict(r, tf32_pred=None, tf32_correct=None, tf32_note="no_model_input"))
            continue
        logits = run_tf32(args.icraft_run, model_json, model_raw, inp,
                          workdir, "c3_%d" % idx)
        pred = argmax(logits)
        results.append(dict(r, tf32_pred=pred,
                            tf32_correct=1 if pred == r["source_class"] else 0,
                            tf32_note="forced" if not r["gated"] else "gated"))
        n_run += 1
    # compare TF32 vs BF16 forced on the samples where both are available
    comp = [x for x in results if x["tf32_pred"] is not None]
    tf32_correct = sum(x["tf32_correct"] for x in comp)
    bf16_forced_correct = sum(x["forced_label_correct"] for x in comp)
    flips = [(x["source_index"], x["modulation"], x["forced_raw24_pred"], x["tf32_pred"])
             for x in comp if x["forced_raw24_pred"] != x["tf32_pred"]]
    print("[C3 dual-SDR] tf32_correct=%d/%d  bf16_forced_correct=%d/%d  argmax_flips=%d %s"
          % (tf32_correct, len(comp), bf16_forced_correct, len(comp), len(flips), flips))
    return {"phase": "c3", "tf32_correct": tf32_correct, "compared": len(comp),
            "bf16_forced_correct": bf16_forced_correct, "argmax_flips": flips,
            "rows": results}


def main(argv) -> int:
    ap = argparse.ArgumentParser(description="tf32-ab1 Phase C offline hard-gate")
    ap.add_argument("--phase", default="all", choices=["c1", "c2", "c3", "all"])
    ap.add_argument("--icraft-run", default="D:/icraft/bin/icraft-run.exe")
    ap.add_argument("--model-dir", default="model_rml24_tf32")
    ap.add_argument("--out-dir", default="results/tf32_ab1_phase_c")
    ap.add_argument("--clean24-dir", default=DEFAULTS["clean24_dir"])
    ap.add_argument("--clean24-bf16-baseline", default=DEFAULTS["clean24_bf16_baseline"])
    ap.add_argument("--scalarwl-dir", default=DEFAULTS["scalarwl_dir"])
    ap.add_argument("--dualsdr-results", default=DEFAULTS["dualsdr_results"])
    args = ap.parse_args(argv)

    args.icraft_run = Path(args.icraft_run)
    if not args.icraft_run.is_file():
        fail("icraft-run.exe not found: %s" % args.icraft_run)
    model_dir = Path(args.model_dir)
    model_json = model_dir / "rml24_adamrv11_tf32.json"
    model_raw = model_dir / "rml24_adamrv11_tf32.raw"
    if not model_json.is_file() or not model_raw.is_file():
        fail("tf32 json/raw not found under %s" % model_dir)
    jsha = hashlib.sha256(model_json.read_bytes()).hexdigest()
    rsha = hashlib.sha256(model_raw.read_bytes()).hexdigest()
    if jsha != TF32_JSON_SHA or rsha != TF32_RAW_SHA:
        fail("TF32 model identity mismatch: json=%s raw=%s" % (jsha, rsha))
    print("[phase-C] tf32 json=%s raw=%s" % (jsha, rsha))

    out = Path(args.out_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    workdir = out / "_work"
    workdir.mkdir(parents=True)

    report = {"tf32_json_sha256": jsha, "tf32_raw_sha256": rsha}
    for phase in ("c1", "c2", "c3"):
        if args.phase not in ("all", phase):
            continue
        fn = {"c1": phase_c1, "c2": phase_c2, "c3": phase_c3}[phase]
        sub = fn(args, model_json, model_raw, workdir, out)
        report[phase] = sub
        (out / ("%s_summary.json" % phase)).write_text(
            json.dumps(sub, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    (out / "phase_c_summary.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("[phase-C] wrote %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
