#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
judge_radioml_dc_singlesdr.py -- 单 SDR DC 适配五臂判定器
(fix10class24-original-radioml-dc-ab1, 单 SDR 优先部分)。

五臂走同一批 frozen 原始 RadioML (同一 hdf5_row_index / X[row].T 合同 /
model_input_sha256), 回答「移除 DC -> TX AC -> RX 还原尺度 + 加回 DC」这条链相对
Host 参考、数字无 RF、以及 direct(逐字节不变) 单 SDR 链的准确率变化。

臂:
  A         = npu-ab1 manifest 的 host_pred (Host BF16 参考), 仅参考, 绝不替代板端。
  D-direct  = dc 数字回环的 direct_pred (数字无 RF, direct 路径, digital_predictions_dc.tsv)。
  D-dc      = dc 数字回环的 dc_pred (数字无 RF, dc-transport 路径)。
  S-direct  = 板端单 SDR --adaptation=direct 的 board_results.tsv (19 列契约 §4)。
  S-dc      = 板端单 SDR --adaptation=dc-transport 的 board_results.tsv。

诚实边界:
  * gate-reject 记作端到端失败 (分母不剔除); hard_invalid 绝不强制为成功。
  * 强制分类诊断仅当恢复数据有效 (residual in (0.100,0.30]); 由板端 hard_invalid 字段
    直接决定, 本判定器绝不复算或推翻它。
  * dataset_snr_db 是数据集标称 SNR, 不是真实 RX SNR。
  * 数字验证 (D-direct/D-dc) 只证明 DC 适配的确定性往返; 生产恢复在无 RF 时退化为
    恒等, 不声明 C++ 恢复的 Python 等效物。

用法:
    python -I scripts/judge_radioml_dc_singlesdr.py \
        --input-package <npu-ab1 input_package dir> \
        --digital <dc digital_predictions_dc.tsv> \
        [--board-direct <direct board_results.tsv>] \
        [--board-dc <dc-transport board_results.tsv>] \
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

# 19 列 board_results.tsv (契约 §4), direct / dc-transport 两个板端运行共用同一格式。
BOARD_COLS = [
    "selection_id", "hdf5_row_index", "raw24_class", "dataset_snr_db", "gated",
    "board_pred", "finite", "residual", "corr", "coarse_cfo_hz", "fine_cfo_hz",
    "total_cfo_hz", "fractional_timing_samples", "clip", "capture_attempts",
    "gate_reject", "hard_invalid", "tx_stop_ok", "rx_restore_ok",
]

# digital_predictions_dc.tsv 的预测列 (由 scripts/digital_roundtrip_radioml_dc.py 产生)。
DIGITAL_PRED_COLS = ["direct_pred", "dc_pred"]


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


def _i(v):
    """int 或 None (空/非数字)。"""
    if v is None or v == "":
        return None
    try:
        return int(v)
    except ValueError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-package", required=True)
    ap.add_argument("--digital", required=True)
    ap.add_argument("--board-direct", default="")
    ap.add_argument("--board-dc", default="")
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

    digital = load_tsv_dict(Path(args.digital),
                            ["selection_id"] + DIGITAL_PRED_COLS)

    def load_board(path):
        if not path:
            return None
        return load_tsv_dict(Path(path), [
            "selection_id", "gated", "board_pred", "finite", "residual", "corr",
            "capture_attempts", "gate_reject", "hard_invalid", "tx_stop_ok",
            "rx_restore_ok"])

    board_direct = load_board(args.board_direct)
    board_dc = load_board(args.board_dc)

    # ---- 每帧五臂预测 ----
    per = []
    for fr in frames:
        sid = fr["selection_id"]
        a_pred = fr["host_pred"]
        dd_pred = _i(digital[sid]["direct_pred"]) if sid in digital else None
        dc_pred = _i(digital[sid]["dc_pred"]) if sid in digital else None
        row = {
            "sid": sid, "label": fr["raw24_class"], "snr": fr["dataset_snr_db"],
            "a_pred": a_pred,
            "dd_pred": dd_pred, "dc_pred": dc_pred,
            "sd_pred": None, "sd_gated": None, "sd_residual": None, "sd_corr": None,
            "sd_reject": None, "sd_invalid": None, "sd_attempts": None, "sd_present": False,
            "sc_pred": None, "sc_gated": None, "sc_residual": None, "sc_corr": None,
            "sc_reject": None, "sc_invalid": None, "sc_attempts": None, "sc_present": False,
        }
        for key, board in (("sd", board_direct), ("sc", board_dc)):
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
    cov_dd = sum(1 for r in per if r["dd_pred"] is not None)
    cov_dc = sum(1 for r in per if r["dc_pred"] is not None)
    cov_sd = sum(1 for r in per if r["sd_present"])
    cov_sc = sum(1 for r in per if r["sc_present"])

    # ---- 各臂正确率口径 ----
    def correct(arm, r):
        if arm == "A":
            return r["a_pred"] == r["label"]
        if arm == "D-direct":
            return r["dd_pred"] is not None and r["dd_pred"] == r["label"]
        if arm == "D-dc":
            return r["dc_pred"] is not None and r["dc_pred"] == r["label"]
        if arm == "S-direct":
            return r["sd_pred"] is not None and r["sd_pred"] == r["label"]
        if arm == "S-dc":
            return r["sc_pred"] is not None and r["sc_pred"] == r["label"]
        raise ValueError(arm)

    acc_a = sum(correct("A", r) for r in per) / n
    acc_dd = (sum(correct("D-direct", r) for r in per) / cov_dd
              if cov_dd else float("nan"))
    acc_dc = (sum(correct("D-dc", r) for r in per) / cov_dc
              if cov_dc else float("nan"))

    def arm_metrics(arm):
        key = {"S-direct": "sd", "S-dc": "sc"}[arm]
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

    sd_m = arm_metrics("S-direct")
    sc_m = arm_metrics("S-dc")

    def flip(a_arm, b_arm):
        def pred(arm, r):
            return {"A": r["a_pred"], "D-direct": r["dd_pred"], "D-dc": r["dc_pred"],
                    "S-direct": r["sd_pred"], "S-dc": r["sc_pred"]}[arm]
        return sum(1 for r in per
                   if pred(a_arm, r) is not None and pred(b_arm, r) is not None
                   and pred(a_arm, r) != pred(b_arm, r))

    flips = {
        "A_to_D_direct": flip("A", "D-direct"),
        "A_to_D_dc": flip("A", "D-dc"),
        "A_to_S_direct": flip("A", "S-direct"),
        "A_to_S_dc": flip("A", "S-dc"),
        "D_direct_to_S_direct": flip("D-direct", "S-direct"),
        "D_dc_to_S_dc": flip("D-dc", "S-dc"),
        # 核心对照: 单 SDR RF 链上 direct vs dc-transport 是否翻转
        "S_direct_to_S_dc": flip("S-direct", "S-dc"),
        "D_direct_to_D_dc": flip("D-direct", "D-dc"),
    }

    def confusion(arm):
        key = {"S-direct": "sd", "S-dc": "sc"}[arm]
        conf = np.zeros((C.N_CLASSES, C.N_CLASSES), dtype=np.int64)
        for r in per:
            if r[key + "_pred"] is not None:
                conf[r["label"], r[key + "_pred"]] += 1
        return conf

    conf_sd = confusion("S-direct")
    conf_sc = confusion("S-dc")

    per_class = {}
    for c in range(C.N_CLASSES):
        rs = [r for r in per if r["label"] == c]
        per_class[C.LABEL_ORDER_24[c]] = {
            "n": len(rs),
            "a_correct": sum(correct("A", r) for r in rs),
            "d_direct_correct": sum(correct("D-direct", r) for r in rs),
            "d_dc_correct": sum(correct("D-dc", r) for r in rs),
            "s_direct_present": sum(1 for r in rs if r["sd_present"]),
            "s_direct_e2e_correct": sum(1 for r in rs if r["sd_present"]
                                        and r["sd_gated"] == 1 and r["sd_pred"] == r["label"]),
            "s_dc_present": sum(1 for r in rs if r["sc_present"]),
            "s_dc_e2e_correct": sum(1 for r in rs if r["sc_present"]
                                    and r["sc_gated"] == 1 and r["sc_pred"] == r["label"]),
        }

    def resid_corr_stats(arm):
        key = {"S-direct": "sd", "S-dc": "sc"}[arm]
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
        "token": "M29-RML24-FIX10CLASS24-ORIGINAL-RADIOML-DC-AB1-SINGLESDR-JUDGED",
        "arm_s_direct_pending": not bool(board_direct),
        "arm_s_dc_pending": not bool(board_dc),
        "coverage": {"A": cov_a, "D_direct": cov_dd, "D_dc": cov_dc,
                     "S_direct": cov_sd, "S_dc": cov_sc},
        "accuracy": {
            "A_host_bf16_reference": acc_a,
            "D_direct_digital": acc_dd,
            "D_dc_digital": acc_dc,
            "S_direct": sd_m,
            "S_dc": sc_m,
        },
        "prediction_flips": flips,
        "residual_corr_S_direct": resid_corr_stats("S-direct"),
        "residual_corr_S_dc": resid_corr_stats("S-dc"),
        "per_class": per_class,
        "note": ("arm A host_pred 仅参考; dataset_snr_db 非真实 RX SNR; "
                 "gate-reject=端到端失败; hard_invalid 绝不强制为成功; "
                 "D-direct/D-dc 是数字无 RF 确定性往返, 不声明生产恢复等效"),
    }
    with open(out / "judge_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    def write_confusion(arm, conf):
        with open(out / ("confusion_%s.tsv" % arm.lower()), "w", encoding="utf-8") as f:
            f.write("true_class\t" + "\t".join(C.LABEL_ORDER_24) + "\n")
            for i in range(C.N_CLASSES):
                f.write(C.LABEL_ORDER_24[i] + "\t" +
                        "\t".join(str(conf[i, j]) for j in range(C.N_CLASSES)) + "\n")

    write_confusion("S_direct", conf_sd)
    write_confusion("S_dc", conf_sc)

    def fmt(x):
        return ("%.4f" % x) if x == x else "PENDING"

    print("RADIOML_DC_SINGLESDR_JUDGE arm_s_direct_pending=%s arm_s_dc_pending=%s "
          "coverage_A=%d coverage_D_direct=%d coverage_D_dc=%d coverage_S_direct=%d "
          "coverage_S_dc=%d acc_A=%.4f acc_D_direct=%s acc_D_dc=%s "
          "acc_S_direct_e2e=%s acc_S_dc_e2e=%s flips_S_direct_to_S_dc=%d out_dir=%s" %
          (summary["arm_s_direct_pending"], summary["arm_s_dc_pending"],
           cov_a, cov_dd, cov_dc, cov_sd, cov_sc, acc_a, fmt(acc_dd), fmt(acc_dc),
           fmt(sd_m["end_to_end_gate_reject_is_fail"]),
           fmt(sc_m["end_to_end_gate_reject_is_fail"]),
           flips["S_direct_to_S_dc"], out))
    print("RADIOML_DC_SINGLESDR_JUDGE_DONE")


if __name__ == "__main__":
    main()
