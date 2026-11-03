#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
replay_o0_production.py -- Phase 1：完整重放当前生产恢复，记为 O0_BLIND。

要求：对每帧，主机重放张量 SHA 与原保存生产张量（board model_input_sha256）逐字节
一致；rf_fix2_target 应复现 23/24 过门、1/24 正确的基本事实。
任何一帧不能复现 -> INVALID_ANALYSIS_PRODUCTION_REPLAY_MISMATCH（rc!=0，fail-closed）。

产出 results/o0_replay.tsv。
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracle_common as OC  # noqa: E402

OUT_DIR = Path(__file__).resolve().parent.parent / "results"

HEADER = ["session_id", "source_index", "class_index", "class_name",
          "timing_offset", "coarse_cfo_hz", "fractional_timing", "a_real", "a_imag",
          "b_real", "b_imag", "training_residual_rel", "replayed_sha256",
          "board_sha256", "byte_exact", "gated", "board_pred", "label_correct"]


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / "o0_replay.tsv"
    rows = []
    n_byte = 0
    per_sess = {}
    for sess in OC.SESSIONS:
        board = OC.load_board_rows(sess["capture_dir"])
        cap = Path(sess["capture_dir"])
        ok, correct, gated = 0, 0, 0
        for sid in range(1, 25):
            br = board[sid]
            rx_full = OC.read_raw_complex(cap / ("%d.raw.i16" % sid))
            off, _ = OC.locate_preamble(rx_full, len(rx_full) - OC.K_TOTAL)
            rx_burst = rx_full[off:off + OC.K_TOTAL].copy()

            if sess["chain"] == "fix2":
                est = __import__("oracle_common", fromlist=["FIX2"]).FIX2.estimate_public_reference_fix2(rx_burst)
            else:
                est = OC.IRX.estimate_public_reference(rx_burst)

            zi = OC.recover_o0(sess["chain"], rx_burst, est)
            replayed_sha = OC.sha256_bytes(OC.tensor_to_bytes(zi))
            board_sha = br["model_input_sha256"]
            byte_exact = (replayed_sha == board_sha)
            ok += byte_exact
            n_byte += byte_exact

            pred = int(br["board_pred"])
            label = int(br["class_index"])
            is_correct = (pred == label)
            correct += is_correct
            is_gated = int(br["gated"]) == 1
            gated += is_gated

            a, b = est["a"], est["b"]
            rows.append([
                sess["name"], sid, label, br["class_name"],
                est["timing_offset"], est["coarse_cfo_hz"],
                est.get("fractional_timing", ""), a.real, a.imag, b.real, b.imag,
                est.get("training_residual_rel", ""), replayed_sha, board_sha,
                int(byte_exact), br["gated"], pred, int(is_correct),
            ])
        per_sess[sess["name"]] = {
            "byte_exact": "%d/24" % ok, "gate": "%d/24" % gated,
            "label_correct": "%d/24" % correct,
        }

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\t".join(HEADER) + "\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")

    print("o0_replay.tsv -> %s" % out_path)
    for name, s in per_sess.items():
        print("  %s: byte_exact=%s gate=%s label_correct=%s" %
              (name, s["byte_exact"], s["gate"], s["label_correct"]))

    # Phase 1 fail-closed 判决
    if n_byte != 48:
        print("\nINVALID_ANALYSIS_PRODUCTION_REPLAY_MISMATCH: byte_exact %d/48" % n_byte)
        return 2

    # 基本事实复核（fix2 应为 23/24 过门、1/24 正确）
    fix2 = per_sess["rf_fix2_target"]
    if fix2["gate"] != "23/24" or fix2["label_correct"] != "1/24":
        print("\nWARNING: rf_fix2_target 基本事实与预期不符 (gate=%s correct=%s)"
              % (fix2["gate"], fix2["label_correct"]))
    print("\nPHASE1-O0-BLIND-BYTEEXACT-PASS: %d/48" % n_byte)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
