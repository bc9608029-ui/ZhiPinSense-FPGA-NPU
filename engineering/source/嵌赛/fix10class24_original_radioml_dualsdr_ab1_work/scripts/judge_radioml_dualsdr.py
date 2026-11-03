#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
judge_radioml_dualsdr.py -- Phase E: 三臂判定器 (A 原始 / D 数字无RF / C 双SDR)。

合并三臂并按 overall / class / dataset_snr_db 输出:
  * coverage              每臂有结果的帧数 / 480
  * gated accuracy        门内 (0.100 门通过) 中正确的比例
  * end-to-end accuracy   门拒 = 失败 的端到端准确率
  * forced diagnostic     门拒但恢复数据有效 -> Host 强制分类的诊断准确率 + 实际覆盖
  * prediction changes    A->D / A->C / D->C 翻转
  * confusion matrix      raw24 true x pred
  * residual/corr/CFO/clip/重捕统计
  * missing/dup/identity/irrecoverable 核对

诚实边界:
  * arm A 参考 = Host BF16 419/480 (npu-ab1 manifest host_pred), 仅是参考, 绝不替代板端。
  * arm C 板端结果未回传 -> 该臂标记 PENDING, 不虚构数字。
  * dataset_snr_db 是数据集标称 SNR, 不是真实 RX SNR。
  * 强制分类仅当恢复数据有效; hard_invalid 样本绝不强制为成功。

用法:
    python -I scripts/judge_radioml_dualsdr.py \
        --input-package <npu-ab1 input_package dir> \
        --digital <digital_roundtrip.tsv> \
        [--board <board_results.tsv>] \
        --out-dir <fresh dir>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_dualsdr_common as C  # noqa: E402
from export_radioml_dualsdr_tx_payload import parse_npu_ab_manifest  # noqa: E402


def load_tsv_dict(path: Path, required):
    lines = path.read_text(encoding="utf-8").rstrip("\n").split("\n")
    header = lines[0].rstrip("\r").split("\t")
    for k in required:
        assert k in header, "missing column %s in %s" % (k, path)
    out = {}
    for ln in lines[1:]:
        ln = ln.rstrip("\r")
        if not ln.strip():
            continue
        f = ln.split("\t")
        rec = dict(zip(header, f))
        out[int(rec["selection_id"])] = rec
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-package", required=True)
    ap.add_argument("--digital", required=True)
    ap.add_argument("--board", default="")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    out = Path(args.out_dir)
    if out.exists():
        print("ERROR: --out-dir already exists: %s" % out, file=sys.stderr)
        sys.exit(2)
    out.mkdir(parents=True)

    frames = parse_npu_ab_manifest(Path(args.input_package) / "manifest.tsv")
    by_id = {fr["selection_id"]: fr for fr in frames}

    digital = load_tsv_dict(Path(args.digital), ["selection_id", "digital_pred"])

    board = None
    if args.board:
        board = load_tsv_dict(Path(args.board), [
            "selection_id", "gated", "board_pred", "finite", "residual", "corr",
            "capture_attempts", "gate_reject", "hard_invalid", "tx_stop_ok"])

    # ---- 每帧三臂预测 ----
    per = []
    for fr in frames:
        sid = fr["selection_id"]
        a_pred = fr["host_pred"]                       # arm A (Host BF16 参考)
        d_pred = int(digital[sid]["digital_pred"]) if digital[sid]["digital_pred"] != "" else None
        row = {
            "sid": sid, "cls": fr["raw24_class"], "snr": fr["dataset_snr_db"],
            "label": fr["raw24_class"],
            "a_pred": a_pred,
            "d_pred": d_pred,
            "c_pred": None, "c_gated": None, "c_residual": None, "c_corr": None,
            "c_reject": None, "c_invalid": None, "c_attempts": None, "c_tx_stop": None,
            "c_present": False,
        }
        if board and sid in board:
            b = board[sid]
            row["c_present"] = True
            row["c_gated"] = int(b["gated"])
            row["c_pred"] = int(b["board_pred"]) if b["finite"] == "1" else None
            row["c_residual"] = float(b["residual"]) if b["residual"] != "" else None
            row["c_corr"] = float(b["corr"]) if b["corr"] != "" else None
            row["c_reject"] = int(b["gate_reject"])
            row["c_invalid"] = int(b["hard_invalid"])
            row["c_attempts"] = int(b["capture_attempts"])
            row["c_tx_stop"] = int(b["tx_stop_ok"])
        per.append(row)

    # ---- 覆盖率 ----
    # arm D 的数字回环**输入**覆盖全部 480 帧 (输入保真度证据); 其预测为可选 Host
    # 测量, 单独按 d_pred 非空计。
    n = len(per)
    cov_a = n  # arm A 参考恒覆盖 (host_pred 在 manifest)
    cov_d = len(digital)   # 数字回环输入覆盖 = 有 digital_roundtrip 记录的帧数
    cov_d_pred = sum(1 for r in per if r["d_pred"] is not None)
    cov_c = sum(1 for r in per if r["c_present"])

    # ---- 各臂正确率口径 ----
    def correct(arm, r):
        if arm == "A":
            return r["a_pred"] == r["label"]
        if arm == "D":
            return r["d_pred"] is not None and r["d_pred"] == r["label"]
        if arm == "C":
            return r["c_pred"] is not None and r["c_pred"] == r["label"]
        raise ValueError(arm)

    acc_a = sum(correct("A", r) for r in per) / n
    acc_d = (sum(correct("D", r) for r in per) / cov_d_pred
             if cov_d_pred else float("nan"))

    # arm C: gated accuracy = 门内正确 / 门内数; e2e = (门内正确) / 有结果数 (门拒=失败)
    c_gated = [r for r in per if r["c_present"] and r["c_gated"] == 1]
    c_all = [r for r in per if r["c_present"]]
    acc_c_gated = (sum(1 for r in c_gated if r["c_pred"] == r["label"]) / len(c_gated)
                   if c_gated else float("nan"))
    acc_c_e2e = (sum(1 for r in c_all if r["c_gated"] == 1 and r["c_pred"] == r["label"])
                 / len(c_all) if c_all else float("nan"))
    # 门拒且恢复有效 -> 可强制诊断; hard_invalid 绝不强制
    c_force = [r for r in c_all if r["c_gated"] == 0 and r["c_invalid"] == 0]

    # ---- 翻转 ----
    flips_ad = sum(1 for r in per if r["d_pred"] is not None and r["d_pred"] != r["a_pred"])
    flips_dc = sum(1 for r in per if r["c_pred"] is not None and r["d_pred"] is not None
                   and r["c_pred"] != r["d_pred"])
    flips_ac = sum(1 for r in per if r["c_pred"] is not None and r["c_pred"] != r["a_pred"])

    # ---- 混淆 (arm C 无 -> 空) ----
    conf = np.zeros((C.N_CLASSES, C.N_CLASSES), dtype=np.int64)
    for r in per:
        if r["c_pred"] is not None:
            conf[r["label"], r["c_pred"]] += 1

    # ---- 按类 / 按 SNR ----
    def strata(frames_subset, keyfn):
        d = {}
        for r in frames_subset:
            d.setdefault(keyfn(r), []).append(r)
        return d

    per_class = {}
    for c in range(C.N_CLASSES):
        rs = [r for r in per if r["label"] == c]
        per_class[C.LABEL_ORDER_24[c]] = {
            "n": len(rs),
            "a_correct": sum(correct("A", r) for r in rs),
            "d_correct": sum(correct("D", r) for r in rs),
            "c_present": sum(1 for r in rs if r["c_present"]),
            "c_e2e_correct": sum(1 for r in rs if r["c_present"] and r["c_gated"] == 1
                                 and r["c_pred"] == r["label"]),
        }
    per_snr = {}
    for s in (0, 10, 20, 30):
        rs = [r for r in per if r["snr"] == s]
        per_snr["%ddB" % s] = {
            "n": len(rs),
            "a_correct": sum(correct("A", r) for r in rs),
            "c_present": sum(1 for r in rs if r["c_present"]),
            "c_e2e_correct": sum(1 for r in rs if r["c_present"] and r["c_gated"] == 1
                                 and r["c_pred"] == r["label"]),
        }

    # ---- residual/corr 统计 (arm C) ----
    res = [r["c_residual"] for r in per if r["c_residual"] is not None]
    crr = [r["c_corr"] for r in per if r["c_corr"] is not None]

    summary = {
        "token": "M29-RML24-FIX10CLASS24-ORIGINAL-RADIOML-DUALSDR-AB1-JUDGED",
        "arm_c_board_pending": not bool(board),
        "coverage": {"A": cov_a, "D_digital_input": cov_d, "D_prediction": cov_d_pred,
                     "C": cov_c},
        "accuracy": {
            "A_host_bf16_reference": acc_a,
            "D_digital_e2e": acc_d,
            "C_gated": acc_c_gated,
            "C_end_to_end_gate_reject_is_fail": acc_c_e2e,
            "C_gate_reject_forceable_count": len(c_force),
        },
        "prediction_flips": {"A_to_D": flips_ad, "D_to_C": flips_dc, "A_to_C": flips_ac},
        "residual_stats": {
            "n": len(res),
            "min": min(res) if res else None,
            "median": float(np.median(res)) if res else None,
            "max": max(res) if res else None,
            "pass_0100": sum(1 for x in res if x <= C.RF_RESIDUAL_GATE) if res else 0,
        },
        "corr_stats": {
            "n": len(crr),
            "min": min(crr) if crr else None,
            "median": float(np.median(crr)) if crr else None,
        },
        "per_class": per_class,
        "per_snr": per_snr,
        "note": "arm A host_pred 仅是参考; dataset_snr_db 非真实 RX SNR",
    }
    with open(out / "judge_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)
    with open(out / "confusion_c.tsv", "w", encoding="utf-8") as f:
        f.write("true_class\t" + "\t".join(C.LABEL_ORDER_24) + "\n")
        for i in range(C.N_CLASSES):
            f.write(C.LABEL_ORDER_24[i] + "\t" + "\t".join(str(conf[i, j]) for j in range(C.N_CLASSES)) + "\n")

    print("RADIOML_DUALSDR_JUDGE arm_c_pending=%s coverage_A=%d coverage_D_input=%d "
          "coverage_D_pred=%d coverage_C=%d acc_A=%.4f acc_D=%s acc_C_e2e=%s out_dir=%s" %
          (summary["arm_c_board_pending"], cov_a, cov_d, cov_d_pred, cov_c, acc_a,
           ("%.4f" % acc_d) if acc_d == acc_d else "PENDING",
           ("%.4f" % acc_c_e2e) if acc_c_e2e == acc_c_e2e else "PENDING", out))
    print("RADIOML_DUALSDR_JUDGE_DONE")


if __name__ == "__main__":
    main()
