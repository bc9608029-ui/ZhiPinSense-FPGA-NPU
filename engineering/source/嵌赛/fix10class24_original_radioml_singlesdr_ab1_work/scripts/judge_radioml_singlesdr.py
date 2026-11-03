#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
judge_radioml_singlesdr.py -- 四臂判定器 (fix10class24-original-radioml-singlesdr-ab1):
A 原始参考 / D 数字无 RF / C 双 SDR / S 单 SDR。

四臂走同一批 480 帧原始 RadioML (同一 hdf5_row_index / X[row].T 合同 /
model_input_sha256), 回答「单 SDR 局部 TX -> 同轴 -> 同 SDR RX 恢复」这一条链相对
Host 参考、数字无 RF、双 SDR 三臂的准确率变化 / 哪些类-SNR 稳定 vs 退化。

臂:
  A  = npu-ab1 manifest 的 host_pred (Host BF16 参考 419/480), 仅参考, 绝不替代板端。
  D  = dualsdr 的 digital_roundtrip.tsv (数字无 RF 回环; digital_pred 可能为空 = PENDING)。
  C  = dualsdr 的 board_results.tsv (双 SDR; 19 列契约 §4; 未回传 = PENDING)。
  S  = 本任务的 board_results.tsv (单 SDR; 19 列契约 §4; 未回传 = PENDING)。

诚实边界:
  * gate-reject 记作端到端失败 (分母不剔除); hard_invalid 绝不强制为成功。
  * 强制分类诊断仅当恢复数据有效 (residual in (0.100,0.30]); 由板端 hard_invalid 字段
    直接决定, 本判定器绝不复算或推翻它。
  * dataset_snr_db 是数据集标称 SNR, 不是真实 RX SNR。

用法:
    python -I scripts/judge_radioml_singlesdr.py \
        --input-package <npu-ab1 input_package dir> \
        --digital <dualsdr digital_roundtrip.tsv> \
        [--board-dualsdr <dualsdr board_results.tsv>] \
        [--board-singlesdr <singlesdr board_results.tsv>] \
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

# 19 列 board_results.tsv (契约 §4), 双 SDR / 单 SDR 共用同一格式。
BOARD_COLS = [
    "selection_id", "hdf5_row_index", "raw24_class", "dataset_snr_db", "gated",
    "board_pred", "finite", "residual", "corr", "coarse_cfo_hz", "fine_cfo_hz",
    "total_cfo_hz", "fractional_timing_samples", "clip", "capture_attempts",
    "gate_reject", "hard_invalid", "tx_stop_ok", "rx_restore_ok",
]


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


def _f(v, default=None):
    if v is None or v == "":
        return default
    return float(v)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-package", required=True)
    ap.add_argument("--digital", required=True)
    ap.add_argument("--board-dualsdr", default="")
    ap.add_argument("--board-singlesdr", default="")
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    out = Path(args.out_dir)
    if out.exists():
        print("ERROR: --out-dir already exists: %s" % out, file=sys.stderr)
        sys.exit(2)
    out.mkdir(parents=True)

    frames = parse_npu_ab_manifest(Path(args.input_package) / "manifest.tsv")
    by_id = {fr["selection_id"]: fr for fr in frames}
    n = len(frames)

    digital = load_tsv_dict(Path(args.digital), ["selection_id", "digital_pred"])

    def load_board(path):
        if not path:
            return None
        return load_tsv_dict(Path(path), [
            "selection_id", "gated", "board_pred", "finite", "residual", "corr",
            "capture_attempts", "gate_reject", "hard_invalid", "tx_stop_ok",
            "rx_restore_ok"])

    board_c = load_board(args.board_dualsdr)
    board_s = load_board(args.board_singlesdr)

    # ---- 每帧四臂预测 ----
    per = []
    for fr in frames:
        sid = fr["selection_id"]
        a_pred = fr["host_pred"]
        d_pred = int(digital[sid]["digital_pred"]) \
            if digital[sid]["digital_pred"] != "" else None
        row = {
            "sid": sid, "label": fr["raw24_class"], "snr": fr["dataset_snr_db"],
            "a_pred": a_pred, "d_pred": d_pred,
            "c_pred": None, "c_gated": None, "c_residual": None, "c_corr": None,
            "c_reject": None, "c_invalid": None, "c_attempts": None, "c_present": False,
            "s_pred": None, "s_gated": None, "s_residual": None, "s_corr": None,
            "s_reject": None, "s_invalid": None, "s_attempts": None, "s_present": False,
        }
        for key, board, arm in (("c", board_c, "C"), ("s", board_s, "S")):
            if board and sid in board:
                b = board[sid]
                row[key + "_present"] = True
                row[key + "_gated"] = int(b["gated"])
                row[key + "_pred"] = int(b["board_pred"]) if b["finite"] == "1" else None
                row[key + "_residual"] = _f(b["residual"])
                row[key + "_corr"] = _f(b["corr"])
                row[key + "_reject"] = int(b["gate_reject"])
                row[key + "_invalid"] = int(b["hard_invalid"])
                row[key + "_attempts"] = int(b["capture_attempts"])
        per.append(row)

    # ---- 覆盖率 ----
    cov_a = n
    cov_d_input = len(digital)
    cov_d_pred = sum(1 for r in per if r["d_pred"] is not None)
    cov_c = sum(1 for r in per if r["c_present"])
    cov_s = sum(1 for r in per if r["s_present"])

    # ---- 各臂正确率口径 ----
    def correct(arm, r):
        if arm == "A":
            return r["a_pred"] == r["label"]
        if arm == "D":
            return r["d_pred"] is not None and r["d_pred"] == r["label"]
        if arm in ("C", "S"):
            return r[arm.lower() + "_pred"] is not None and \
                r[arm.lower() + "_pred"] == r["label"]
        raise ValueError(arm)

    acc_a = sum(correct("A", r) for r in per) / n
    acc_d = (sum(correct("D", r) for r in per) / cov_d_pred
             if cov_d_pred else float("nan"))

    def arm_metrics(arm):
        key = arm.lower()
        allrows = [r for r in per if r[key + "_present"]]
        gated = [r for r in allrows if r[key + "_gated"] == 1]
        acc_gated = (sum(1 for r in gated if r[key + "_pred"] == r["label"]) / len(gated)
                     if gated else float("nan"))
        acc_e2e = (sum(1 for r in allrows if r[key + "_gated"] == 1 and
                       r[key + "_pred"] == r["label"]) / len(allrows)
                   if allrows else float("nan"))
        forceable = [r for r in allrows if r[key + "_gated"] == 0 and
                     r[key + "_invalid"] == 0]
        hard_invalid = sum(1 for r in allrows if r[key + "_invalid"] == 1)
        return {
            "present": len(allrows),
            "gated": len(gated),
            "gated_accuracy": acc_gated,
            "end_to_end_gate_reject_is_fail": acc_e2e,
            "gate_reject_forceable_count": len(forceable),
            "hard_invalid_count": hard_invalid,
        }

    c_m = arm_metrics("C")
    s_m = arm_metrics("S")

    # ---- 翻转 ----
    flips = {
        "A_to_D": sum(1 for r in per if r["d_pred"] is not None and r["d_pred"] != r["a_pred"]),
        "A_to_C": sum(1 for r in per if r["c_pred"] is not None and r["c_pred"] != r["a_pred"]),
        "A_to_S": sum(1 for r in per if r["s_pred"] is not None and r["s_pred"] != r["a_pred"]),
        "D_to_C": sum(1 for r in per if r["c_pred"] is not None and r["d_pred"] is not None
                      and r["c_pred"] != r["d_pred"]),
        "D_to_S": sum(1 for r in per if r["s_pred"] is not None and r["d_pred"] is not None
                      and r["s_pred"] != r["d_pred"]),
        "C_to_S": sum(1 for r in per if r["c_pred"] is not None and r["s_pred"] is not None
                      and r["c_pred"] != r["s_pred"]),
    }

    # ---- 混淆 (S 与 C 各一) ----
    def confusion(arm):
        conf = np.zeros((C.N_CLASSES, C.N_CLASSES), dtype=np.int64)
        key = arm.lower()
        for r in per:
            if r[key + "_pred"] is not None:
                conf[r["label"], r[key + "_pred"]] += 1
        return conf

    conf_c = confusion("C")
    conf_s = confusion("S")

    # ---- 按类 / 按 SNR ----
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
            "s_present": sum(1 for r in rs if r["s_present"]),
            "s_e2e_correct": sum(1 for r in rs if r["s_present"] and r["s_gated"] == 1
                                 and r["s_pred"] == r["label"]),
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
            "s_present": sum(1 for r in rs if r["s_present"]),
            "s_e2e_correct": sum(1 for r in rs if r["s_present"] and r["s_gated"] == 1
                                 and r["s_pred"] == r["label"]),
        }

    def resid_corr_stats(arm):
        key = arm.lower()
        res = [r[key + "_residual"] for r in per if r[key + "_residual"] is not None]
        crr = [r[key + "_corr"] for r in per if r[key + "_corr"] is not None]
        return {
            "residual": {
                "n": len(res),
                "min": min(res) if res else None,
                "median": float(np.median(res)) if res else None,
                "max": max(res) if res else None,
                "pass_0100": sum(1 for x in res if x <= C.RF_RESIDUAL_GATE) if res else 0,
            },
            "corr": {
                "n": len(crr),
                "min": min(crr) if crr else None,
                "median": float(np.median(crr)) if crr else None,
            },
        }

    summary = {
        "token": "M29-RML24-FIX10CLASS24-ORIGINAL-RADIOML-SINGLESDR-AB1-JUDGED",
        "arm_s_board_pending": not bool(board_s),
        "arm_c_board_pending": not bool(board_c),
        "coverage": {"A": cov_a, "D_digital_input": cov_d_input,
                     "D_prediction": cov_d_pred, "C": cov_c, "S": cov_s},
        "accuracy": {
            "A_host_bf16_reference": acc_a,
            "D_digital_e2e": acc_d,
            "C": c_m,
            "S": s_m,
        },
        "prediction_flips": flips,
        "residual_corr_S": resid_corr_stats("S"),
        "residual_corr_C": resid_corr_stats("C"),
        "per_class": per_class,
        "per_snr": per_snr,
        "note": ("arm A host_pred 仅参考; dataset_snr_db 非真实 RX SNR; "
                 "gate-reject=端到端失败; hard_invalid 绝不强制为成功"),
    }
    with open(out / "judge_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    def write_confusion(arm, conf):
        with open(out / ("confusion_%s.tsv" % arm.lower()), "w", encoding="utf-8") as f:
            f.write("true_class\t" + "\t".join(C.LABEL_ORDER_24) + "\n")
            for i in range(C.N_CLASSES):
                f.write(C.LABEL_ORDER_24[i] + "\t" +
                        "\t".join(str(conf[i, j]) for j in range(C.N_CLASSES)) + "\n")

    write_confusion("C", conf_c)
    write_confusion("S", conf_s)

    def fmt(x):
        return ("%.4f" % x) if x == x else "PENDING"

    print("RADIOML_SINGLESDR_JUDGE arm_s_pending=%s arm_c_pending=%s "
          "coverage_A=%d coverage_D_input=%d coverage_D_pred=%d coverage_C=%d "
          "coverage_S=%d acc_A=%.4f acc_D=%s acc_C_e2e=%s acc_S_e2e=%s out_dir=%s" %
          (summary["arm_s_board_pending"], summary["arm_c_board_pending"],
           cov_a, cov_d_input, cov_d_pred, cov_c, cov_s, acc_a, fmt(acc_d),
           fmt(c_m["end_to_end_gate_reject_is_fail"]),
           fmt(s_m["end_to_end_gate_reject_is_fail"]), out))
    print("RADIOML_SINGLESDR_JUDGE_DONE")


if __name__ == "__main__":
    main()
