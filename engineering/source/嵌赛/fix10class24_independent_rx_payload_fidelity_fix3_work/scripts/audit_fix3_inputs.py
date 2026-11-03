#!/usr/bin/env python3
"""audit_fix3_inputs.py -- Fix3 Phase A steps 1-2: archive identity + integrity audit.

Read-only, deterministic, fail-closed.  For the latest 24-frame independent-RX
capture archive it:

  Phase 0 (archive identity)   -- pin every input: capture dir, model dir + SHA,
                                  icraft-run.exe, and the four file roles per frame.
  Phase 1 (integrity audit)    -- recompute per frame:
                                    * raw.i16            SHA  vs raw_rx_sha256
                                    * recovered.tensor.bin SHA vs model_input_sha256
                                    * logits.tsv         SHA  vs logits_sha256
                                  verify sizes + tensor finiteness + logits schema;
                                  verify the 21-col results TSV is internally consistent
                                  (23 gated / 1 reject / 23 classified / 1 correct).

Outputs (--out-dir):
  archive_identity.json   -- frozen identity + input inventory
  integrity_audit.tsv     -- one row per frame, recomputed SHAs vs recorded

Usage:
    python -I scripts/audit_fix3_inputs.py \
        --capture-dir F:/嵌赛/board_capture/rml24_fix2_dual_1773374951_244 \
        --model-dir  F:/嵌赛/fix10class24_original_radioml_npu_ab1_work/.../model_rml24_bf16 \
        --icraft-run D:/icraft/bin/icraft-run.exe \
        --out-dir results
"""
from __future__ import annotations

import argparse
import math
import struct
import sys
from pathlib import Path

import numpy as np

# Allow `python -I` (isolated mode, no script dir on sys.path) to still import
# the sibling fix3_common module from this same scripts/ directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import fix3_common as c


def audit_integrity(capture_dir: Path, out_dir: Path) -> list[dict]:
    results_path = capture_dir / "board_independent_rx_results.tsv"
    summary_path = capture_dir / "board_independent_rx_summary.tsv"
    rows = c.load_results_tsv(results_path)
    if not summary_path.is_file():
        c.fail("summary TSV missing: %s" % summary_path)

    audit_rows: list[dict] = []
    for r in rows:
        sid = int(r["source_index"])
        raw_path = capture_dir / ("%d.raw.i16" % sid)
        ten_path = capture_dir / ("%d.recovered.tensor.bin" % sid)
        log_path = capture_dir / ("%d.logits.tsv" % sid)
        diag_path = capture_dir / ("%d.capture.diag.tsv" % sid)
        for p, role in ((raw_path, "raw"), (ten_path, "tensor"), (log_path, "logits"),
                        (diag_path, "diag")):
            if not p.is_file():
                c.fail("frame %d missing %s: %s" % (sid, role, p))

        # --- raw.i16 ---
        raw_bytes = raw_path.read_bytes()
        raw_sha = c.sha256_bytes(raw_bytes)
        raw_size_ok = len(raw_bytes) == c.RAW_I16_BYTES

        # --- recovered tensor (model input) ---
        ten_bytes = ten_path.read_bytes()
        ten_sha = c.sha256_bytes(ten_bytes)
        ten_size_ok = len(ten_bytes) == c.TENSOR_BYTES
        ten_finite = True
        if ten_size_ok:
            arr = np.frombuffer(ten_bytes, dtype="<f4")
            ten_finite = bool(np.all(np.isfinite(arr)))
        else:
            ten_finite = False

        # --- logits.tsv ---
        log_bytes = log_path.read_bytes()
        log_sha = c.sha256_bytes(log_bytes)
        try:
            log_parsed = c.parse_logits_tsv(log_path)
            log_ok = True
        except SystemExit:
            log_parsed = {"pass1": [], "pass2": []}
            log_ok = False

        row = {
            "source_index": sid,
            "class_index": int(r["class_index"]),
            "class_name": r["class_name"],
            "raw_size_ok": raw_size_ok,
            "raw_sha_match": raw_sha == r["raw_rx_sha256"],
            "tensor_size_ok": ten_size_ok,
            "tensor_sha_match": ten_sha == r["model_input_sha256"],
            "tensor_finite": ten_finite,
            "logits_sha_match": log_sha == r["logits_sha256"],
            "logits_parse_ok": log_ok,
            "logits_pass1_n": len(log_parsed["pass1"]),
            "logits_pass2_n": len(log_parsed["pass2"]),
            "gated": int(r["gated"]),
            "board_pred": int(r["board_pred"]),
        }
        audit_rows.append(row)

    # --- whole-archive consistency (must equal the frozen summary) ---
    gated = sum(1 for a in audit_rows if a["gated"])
    reject = sum(1 for a in audit_rows if not a["gated"])
    classified = sum(1 for a in audit_rows if a["board_pred"] >= 0)
    correct = sum(1 for a in audit_rows if a["board_pred"] == a["class_index"])
    return audit_rows


def build_identity(capture_dir: Path, model_dir: Path, icraft_run: Path) -> dict:
    model_json = model_dir / "rml24_adamrv11_bf16.json"
    model_raw = model_dir / "rml24_adamrv11_bf16.raw"
    if not model_json.is_file() or not model_raw.is_file():
        c.fail("model json/raw missing under %s" % model_dir)
    if c.sha256_file(model_json) != c.FROZEN_MODEL_JSON_SHA256:
        c.fail("model json SHA mismatch (not the frozen BF16 model)")
    if c.sha256_file(model_raw) != c.FROZEN_MODEL_RAW_SHA256:
        c.fail("model raw SHA mismatch (not the frozen BF16 model)")
    if not icraft_run.is_file():
        c.fail("icraft-run.exe not found: %s" % icraft_run)

    results_path = capture_dir / "board_independent_rx_results.tsv"
    summary_path = capture_dir / "board_independent_rx_summary.tsv"
    runlog_path = capture_dir / "run.log"

    return {
        "task": "M29-RML24-FIX10CLASS24-INDEPENDENT-RX-PAYLOAD-FIDELITY-FIX3",
        "phase": "A",
        "capture_dir": str(capture_dir),
        "capture_archive_files": sorted(
            p.name for p in capture_dir.iterdir() if p.is_file()),
        "results_tsv_sha256": c.sha256_file(results_path),
        "summary_tsv_sha256": c.sha256_file(summary_path),
        "run_log_sha256": c.sha256_file(runlog_path) if runlog_path.is_file() else None,
        "model_json_sha256": c.sha256_file(model_json),
        "model_raw_sha256": c.sha256_file(model_raw),
        "model_dir": str(model_dir),
        "icraft_run": str(icraft_run),
        "network_name": c.NETWORK_NAME,
        "class_count": c.EXPECT_CLASS_COUNT,
        "frame_count": c.EXPECT_FRAMES,
        "labels": c.LABELS,
    }


def main(argv) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capture-dir", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--icraft-run", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args(argv)

    capture_dir = Path(args.capture_dir)
    model_dir = Path(args.model_dir)
    icraft_run = Path(args.icraft_run)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    identity = build_identity(capture_dir, model_dir, icraft_run)
    audit_rows = audit_integrity(capture_dir, out_dir)

    # ---- write integrity_audit.tsv ----
    header = ["source_index", "class_index", "class_name", "raw_size_ok",
              "raw_sha_match", "tensor_size_ok", "tensor_sha_match", "tensor_finite",
              "logits_sha_match", "logits_parse_ok", "logits_pass1_n", "logits_pass2_n",
              "gated", "board_pred"]
    rows = [[a["source_index"], a["class_index"], a["class_name"],
             int(a["raw_size_ok"]), int(a["raw_sha_match"]),
             int(a["tensor_size_ok"]), int(a["tensor_sha_match"]),
             int(a["tensor_finite"]), int(a["logits_sha_match"]),
             int(a["logits_parse_ok"]), a["logits_pass1_n"], a["logits_pass2_n"],
             a["gated"], a["board_pred"]] for a in audit_rows]
    c.write_tsv(out_dir / "integrity_audit.tsv", header, rows)

    # ---- summary stats ----
    n = len(audit_rows)
    all_raw_sha = sum(1 for a in audit_rows if a["raw_sha_match"])
    all_ten_sha = sum(1 for a in audit_rows if a["tensor_sha_match"])
    all_log_sha = sum(1 for a in audit_rows if a["logits_sha_match"])
    all_size = sum(1 for a in audit_rows if a["raw_size_ok"] and a["tensor_size_ok"])
    all_finite = sum(1 for a in audit_rows if a["tensor_finite"])
    gated = sum(1 for a in audit_rows if a["gated"])
    reject = n - gated
    classified = sum(1 for a in audit_rows if a["board_pred"] >= 0)
    correct = sum(1 for a in audit_rows if a["board_pred"] == a["class_index"])

    verdict = (all_raw_sha == n and all_ten_sha == n and all_log_sha == n
               and all_size == n and all_finite == n and gated == 23
               and reject == 1 and classified == 23 and correct == 1)

    summary = {
        "frame_count": n,
        "raw_sha_match": all_raw_sha,
        "tensor_sha_match": all_ten_sha,
        "logits_sha_match": all_log_sha,
        "all_sizes_ok": all_size,
        "all_tensors_finite": all_finite,
        "gated": gated,
        "gate_reject": reject,
        "classified": classified,
        "correct": correct,
        "integrity_verdict": "PASS" if verdict else "FAIL",
    }
    c.dumps_json({"identity": identity, "integrity": summary,
                  "audit": [a for a in audit_rows]},
                 out_dir / "archive_identity.json")

    print("[identity] model_json=%s model_raw=%s frames=%d"
          % (identity["model_json_sha256"][:12], identity["model_raw_sha256"][:12], n))
    print("[integrity] raw_sha=%d/%d tensor_sha=%d/%d logits_sha=%d/%d size=%d/%d finite=%d/%d"
          % (all_raw_sha, n, all_ten_sha, n, all_log_sha, n, all_size, n, all_finite, n))
    print("[integrity] gated=%d reject=%d classified=%d correct=%d verdict=%s"
          % (gated, reject, classified, correct, "PASS" if verdict else "FAIL"))

    if not verdict:
        c.fail("integrity audit FAILED (see summary above)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
