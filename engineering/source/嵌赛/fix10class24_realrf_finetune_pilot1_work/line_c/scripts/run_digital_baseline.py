#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""run_digital_baseline.py — 并行线 C 职责A：数字基线（960 源 IQ 逐样本 Host BF16）。

对并行线 A 选出的 960 个原始 RadioML 源 IQ（[2,1024] f32 LE，已落盘于
line_a/inputs/S{sn}/{source_id}.bin）逐样本跑冻结 Host BF16（icraft-run --backends
Host，2 遍前向），保存 label / digital_pred / logits / model_input_sha256 /
digital_label_correct。数字基线错误不得删除。

纯离线主机推理，不上板、不发射、不训练。可断点续跑（partial.jsonl）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
LINE_C = HERE.parent
LINE_A = Path(r"F:\嵌赛\fix10class24_realrf_finetune_pilot1_work\line_a")
RESULTS = LINE_C / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

MODEL_JSON = Path(r"F:\嵌赛\fix10class24_original_radioml_npu_ab1_work"
                  r"\sdr_rml24_fix10class24_original_radioml_npu_ab1"
                  r"\model_rml24_bf16\rml24_adamrv11_bf16.json")
MODEL_RAW = Path(r"F:\嵌赛\fix10class24_original_radioml_npu_ab1_work"
                 r"\sdr_rml24_fix10class24_original_radioml_npu_ab1"
                 r"\model_rml24_bf16\rml24_adamrv11_bf16.raw")
FROZEN_JSON_SHA = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
FROZEN_RAW_SHA = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"

NETWORK_NAME = "model_24class"
N_CLASSES = 24
N_PASSES = 2
INPUT_BYTES = 8192

LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
    "FM", "GMSK", "OQPSK",
)


def fatal(msg: str):
    sys.stderr.write("FAIL-CLOSED: %s\n" % msg)
    sys.exit(1)


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_manifest() -> list[dict]:
    path = LINE_A / "results" / "source_manifest_960.tsv"
    lines = [ln.rstrip("\r\n") for ln in path.read_text(encoding="utf-8").splitlines()]
    header = lines[0].split("\t")
    assert header == ["session_id", "source_id", "class_index", "class_name",
                      "dataset_index", "split", "snr_db", "instance",
                      "source_iq_sha256"], f"manifest header mismatch: {header}"
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        rows.append({
            "session_id": f[0], "source_id": f[1], "class_index": int(f[2]),
            "class_name": f[3], "dataset_index": int(f[4]), "split": f[5],
            "snr_db": float(f[6]), "instance": int(f[7]), "source_iq_sha256": f[8],
        })
    assert len(rows) == 960, f"manifest has {len(rows)} rows (want 960)"
    return rows


def run_host_infer(icraft: Path, input_bin: Path, workdir: str):
    log_path = os.path.join(workdir, "logs")
    cmd = [str(icraft), "--json", str(MODEL_JSON), "--raw", str(MODEL_RAW),
           "--network", NETWORK_NAME, "--input", str(input_bin),
           "--backends", "Host", "--dump_output", "--log_path", log_path]
    proc = subprocess.run(cmd, cwd=workdir, capture_output=True)
    if proc.returncode != 0:
        fatal("icraft-run exit %d\n%s\n%s" % (proc.returncode,
              proc.stdout.decode("utf-8", "replace")[-2000:],
              proc.stderr.decode("utf-8", "replace")[-2000:]))
    ftmp_dir = os.path.join(log_path, NETWORK_NAME, "ftmpHQB")
    ftmps = ([os.path.join(ftmp_dir, f) for f in os.listdir(ftmp_dir)]
             if os.path.isdir(ftmp_dir) else [])
    if len(ftmps) != 1:
        fatal("expected 1 ftmp under %s, got %d" % (ftmp_dir, len(ftmps)))
    raw = open(ftmps[0], "rb").read()
    if len(raw) != N_CLASSES * 4:
        fatal("ftmp %s is %d bytes (want %d)" % (ftmps[0], len(raw), N_CLASSES * 4))
    return raw, np.frombuffer(raw, dtype="<f4").astype(np.float64)


def process_one(icraft: Path, rec: dict) -> dict:
    src = LINE_A / "inputs" / rec["session_id"] / f"{rec['source_id']}.bin"
    if not src.is_file():
        fatal("missing source IQ: %s" % src)
    in_bytes = src.read_bytes()
    if len(in_bytes) != INPUT_BYTES:
        fatal("%s is %d bytes (want %d)" % (rec["source_id"], len(in_bytes), INPUT_BYTES))
    if sha256_bytes(in_bytes) != rec["source_iq_sha256"]:
        fatal("%s source_iq_sha256 drift" % rec["source_id"])

    passes = []
    for _ in range(N_PASSES):
        with tempfile.TemporaryDirectory() as td:
            bin_path = Path(td) / "input.bin"
            bin_path.write_bytes(in_bytes)
            raw, logits = run_host_infer(icraft, bin_path, td)
        passes.append({"raw": raw, "logits": logits,
                       "argmax": int(np.argmax(logits)),
                       "finite": bool(np.all(np.isfinite(logits)))})
    p1, p2 = passes[0], passes[1]
    return {
        "source_id": rec["source_id"],
        "class_index": rec["class_index"],
        "class_name": rec["class_name"],
        "dataset_index": rec["dataset_index"],
        "split": rec["split"],
        "label": rec["class_index"],
        "digital_pred": p1["argmax"],
        "digital_label_correct": int(p1["argmax"] == rec["class_index"]),
        "logits": [float(v) for v in p1["logits"]],
        "model_input_sha256": rec["source_iq_sha256"],
        "finite": bool(p1["finite"] and p2["finite"]),
        "repeat_argmax": int(p1["argmax"] == p2["argmax"]),
        "repeat_logits_byte": int(p1["raw"] == p2["raw"]),
        "result_layer": "HOST_BF16",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--icraft-run", default=r"C:\Icraft\CLI v3.39.0\bin\icraft-run.exe")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, default=0, help=">0 = smoke, only first N")
    args = ap.parse_args()

    icraft = Path(args.icraft_run)
    if not icraft.is_file():
        fatal("--icraft-run not found: %s" % icraft)
    if sha256_file(MODEL_JSON) != FROZEN_JSON_SHA:
        fatal("model json SHA mismatch")
    if sha256_file(MODEL_RAW) != FROZEN_RAW_SHA:
        fatal("model raw SHA mismatch")

    recs = read_manifest()
    if args.limit > 0:
        recs = recs[: args.limit]

    partial = RESULTS / "digital_baseline_partial.jsonl"
    done = {}
    if partial.exists():
        for ln in partial.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                r = json.loads(ln)
                done[r["source_id"]] = r
    todo = [r for r in recs if r["source_id"] not in done]
    print("digital_baseline resume: %d done, %d todo" % (len(done), len(todo)))

    if todo:
        buf = []
        def flush():
            if buf:
                with partial.open("a", encoding="utf-8") as f:
                    for r in buf:
                        f.write(json.dumps(r, sort_keys=True) + "\n")
                    f.flush()
                buf.clear()
        if args.workers <= 1:
            for r in todo:
                buf.append(process_one(icraft, r)); flush()
        else:
            with ThreadPoolExecutor(max_workers=args.workers) as ex:
                futs = {ex.submit(process_one, icraft, r): r for r in todo}
                for fut in as_completed(futs):
                    buf.append(fut.result()); flush()

    all_recs = [json.loads(ln) for ln in partial.read_text(encoding="utf-8").splitlines() if ln.strip()]
    all_recs.sort(key=lambda r: r["source_id"])

    cols = ["source_id", "class_index", "class_name", "dataset_index", "split",
            "label", "digital_pred", "digital_label_correct", "model_input_sha256",
            "finite", "repeat_argmax", "repeat_logits_byte", "result_layer"] + \
           [f"logit_{k:02d}" for k in range(N_CLASSES)]
    out = RESULTS / "digital_baseline_960.tsv"
    with out.open("w", encoding="utf-8", newline="") as f:
        f.write("\t".join(cols) + "\n")
        for r in all_recs:
            row = [r["source_id"], r["class_index"], r["class_name"], r["dataset_index"],
                   r["split"], r["label"], r["digital_pred"], r["digital_label_correct"],
                   r["model_input_sha256"], r["finite"], r["repeat_argmax"],
                   r["repeat_logits_byte"], r["result_layer"]] + \
                  ["%.17g" % v for v in r["logits"]]
            f.write("\t".join(str(c) for c in row) + "\n")

    n = len(all_recs)
    n_corr = sum(r["digital_label_correct"] for r in all_recs)
    print("digital_baseline OK: samples=%d correct=%d/%d" % (n, n_corr, n))
    return 0


if __name__ == "__main__":
    sys.exit(main())
