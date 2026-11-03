#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
judge_radioml_gate_separation.py -- 分类门与保真门分离的统一判定器
(fix10class24-classification-gate-separation1)。

对每条板端臂 {single,dual} x {direct,dc-transport}, 同时读入三类结果, 比较
「保真门内分类(生产) / 诊断旁路分类(Part B) / 盲分类(Part A, 无保真门)」的覆盖率与
准确率, 回答: 分类门是否被保真门拖累, 诊断旁路能补回多少。

三类输入 (均按 selection_id 对齐到同一批 480 帧 frozen 原始 RadioML):

  board_results.tsv          19 列生产契约 §4 (board_pred/gated/gate_reject 不变)
  board_diagnostic_results.tsv  12 列 Part B 诊断输出 (classification_layer=
                              NPU_BF16_DIAGNOSTIC, diagnostic_gate_bypass=1)
  blind board_results.tsv    19 列 Part A 盲 RX (residual/corr/cfo = NA / NOT_APPLICABLE)

统一口径 (与 dc 判定器一致):
  * gate-reject 记端到端失败 (分母不剔除); hard_invalid 绝不强制为成功。
  * 缺失输入 = PENDING, 绝不 auto-success。
  * dataset_snr_db 是数据集标称 SNR, 不是真实 RX SNR。

用法:
    python -I scripts/judge_radioml_gate_separation.py \
        --input-package <npu-ab1 input_package> \
        --out-dir <fresh dir> \
        [--board-single-direct <board_results.tsv>] \
        [--diag-single-direct <board_diagnostic_results.tsv>] \
        [--blind-single-direct <blind board_results.tsv>] \
        [--runner-summary-single-direct <runner summary.json>] \
        ... (同样适用于 single-dc / dual-direct / dual-dc)
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

# 19 列生产 board_results.tsv (契约 §4, 生产/盲共用同一形状)。
BOARD_COLS = [
    "selection_id", "hdf5_row_index", "raw24_class", "dataset_snr_db", "gated",
    "board_pred", "finite", "residual", "corr", "coarse_cfo_hz", "fine_cfo_hz",
    "total_cfo_hz", "fractional_timing_samples", "clip", "capture_attempts",
    "gate_reject", "hard_invalid", "tx_stop_ok", "rx_restore_ok",
]

# 12 列 Part B 诊断输出 (board_diagnostic_results.tsv)。
DIAG_COLS = [
    "selection_id", "hdf5_row_index", "raw24_class", "dataset_snr_db", "residual",
    "corr", "board_pred_diag", "finite_diag", "repeat_deterministic",
    "classification_layer", "diagnostic_gate_bypass", "label_correct",
]

# 盲 RX 帧里 residual/corr/cfo 的占位值 (Part A: 训练残差 NA)。
BLIND_NA_TOKENS = {"NA", "N/A", "NOT_APPLICABLE", "nan", ""}

ARM_KEYS = ["single_direct", "single_dc", "dual_direct", "dual_dc"]

# runner summary.json 里的六项统计 (权威; refused/apply_failed 不在诊断 TSV 内)。
SIX_STAT_KEYS = [
    "diagnostic_bypass_total", "diagnostic_bypass_classified",
    "diagnostic_bypass_correct", "diagnostic_bypass_accuracy",
    "diagnostic_bypass_repeat_deterministic", "diagnostic_bypass_refused",
]


def _parse_rows(path: Path, required):
    """读 TSV 为 {selection_id: dict}, fail-closed 校验必需列。"""
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
        out[int(f[header.index("selection_id")])] = dict(zip(header, f))
    return out


def _i(v):
    if v is None or v == "":
        return None
    try:
        return int(v)
    except ValueError:
        return None


def _f(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def load_production(path):
    """19 列生产 board_results.tsv -> {sid: rec} (gated/board_pred/finite/...)。"""
    if not path:
        return None
    return _parse_rows(Path(path), [
        "selection_id", "gated", "board_pred", "finite", "residual", "corr",
        "capture_attempts", "gate_reject", "hard_invalid", "tx_stop_ok",
        "rx_restore_ok"])


def load_diagnostic(path):
    """12 列 Part B 诊断 TSV -> {sid: rec}。"""
    if not path:
        return None
    return _parse_rows(Path(path), [
        "selection_id", "residual", "corr", "board_pred_diag", "finite_diag",
        "repeat_deterministic", "classification_layer", "diagnostic_gate_bypass",
        "label_correct"])


def load_blind(path):
    """19 列 Part A 盲 RX TSV -> {sid: rec} (residual/corr/cfo = NA 允许)。"""
    if not path:
        return None
    return _parse_rows(Path(path), [
        "selection_id", "board_pred", "finite", "residual"])


def _is_blind_na(v):
    return v is None or str(v).strip().upper() in BLIND_NA_TOKENS


def production_metrics(per, key):
    """生产臂指标 (gated 覆盖率 + 门内准确率 + 端到端准确率 + forceable/hard_invalid)。"""
    rows = [r for r in per if r[key + "_present"]]
    gated = [r for r in rows if r[key + "_gated"] == 1]
    acc_gated = (sum(1 for r in gated if r[key + "_pred"] == r["label"]) / len(gated)
                 if gated else float("nan"))
    acc_e2e = (sum(1 for r in rows if r[key + "_gated"] == 1 and
                    r[key + "_pred"] == r["label"]) / len(rows)
               if rows else float("nan"))
    forceable = [r for r in rows if r[key + "_gated"] == 0 and
                 r[key + "_invalid"] == 0]
    hard_invalid = sum(1 for r in rows if r[key + "_invalid"] == 1)
    return {
        "present": len(rows),
        "gated": len(gated),
        "gated_accuracy": acc_gated,
        "end_to_end_gate_reject_is_fail": acc_e2e,
        "gate_reject_forceable_count": len(forceable),
        "hard_invalid_count": hard_invalid,
    }


def diagnostic_metrics(per, key):
    """Part B 诊断臂指标 (六项统计中 TSV 可导出的五项; refused/apply_failed 见 summary)。"""
    rows = [r for r in per if r[key + "_diag_present"]]
    classified = sum(1 for r in rows if r[key + "_diag_finite"] == 1)
    correct = sum(1 for r in rows if r[key + "_diag_label_correct"] == 1)
    repeat = sum(1 for r in rows if r[key + "_diag_repeat"] == 1)
    non_finite = sum(1 for r in rows if r[key + "_diag_finite"] == 0)
    acc = (correct / classified) if classified else float("nan")
    return {
        "present": len(rows),
        "classified": classified,
        "correct": correct,
        "accuracy": acc,
        "repeat_deterministic": repeat,
        "non_finite": non_finite,
    }


def blind_metrics(per, key):
    """Part A 盲臂指标 (无保真门; 每行 finite 即分类)。"""
    rows = [r for r in per if r[key + "_blind_present"]]
    classified = sum(1 for r in rows if r[key + "_blind_pred"] is not None)
    correct = sum(1 for r in rows if r[key + "_blind_pred"] is not None and
                  r[key + "_blind_pred"] == r["label"])
    acc = (correct / classified) if classified else float("nan")
    residual_na = sum(1 for r in rows if r[key + "_blind_residual_na"])
    return {
        "present": len(rows),
        "classified": classified,
        "correct": correct,
        "accuracy": acc,
        "residual_is_na_count": residual_na,
    }


def build_per_frame(frames, arms):
    """把 480 帧与各臂三类输入合并为 per 列表。"""
    per = []
    for fr in frames:
        sid = fr["selection_id"]
        r = {"sid": sid, "label": fr["raw24_class"], "snr": fr["dataset_snr_db"],
             "host_pred": fr["host_pred"]}
        for key in ARM_KEYS:
            a = arms[key]
            # 生产
            b = a.get("board")
            r[key + "_present"] = bool(b and sid in b)
            if r[key + "_present"]:
                bb = b[sid]
                r[key + "_gated"] = int(bb["gated"])
                r[key + "_pred"] = (int(bb["board_pred"])
                                    if bb["finite"] == "1" else None)
                r[key + "_invalid"] = int(bb["hard_invalid"])
            else:
                r[key + "_gated"] = None
                r[key + "_pred"] = None
                r[key + "_invalid"] = None
            # 诊断
            d = a.get("diag")
            r[key + "_diag_present"] = bool(d and sid in d)
            if r[key + "_diag_present"]:
                dd = d[sid]
                r[key + "_diag_pred"] = int(dd["board_pred_diag"])
                r[key + "_diag_finite"] = int(dd["finite_diag"])
                r[key + "_diag_repeat"] = int(dd["repeat_deterministic"])
                r[key + "_diag_label_correct"] = int(dd["label_correct"])
            else:
                r[key + "_diag_pred"] = None
                r[key + "_diag_finite"] = None
                r[key + "_diag_repeat"] = None
                r[key + "_diag_label_correct"] = None
            # 盲
            bl = a.get("blind")
            r[key + "_blind_present"] = bool(bl and sid in bl)
            if r[key + "_blind_present"]:
                bbl = bl[sid]
                r[key + "_blind_pred"] = (_i(bbl["board_pred"])
                                          if bbl["finite"] == "1" else None)
                r[key + "_blind_residual_na"] = _is_blind_na(bbl["residual"])
            else:
                r[key + "_blind_pred"] = None
                r[key + "_blind_residual_na"] = None
        per.append(r)
    return per


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-package", required=True)
    ap.add_argument("--out-dir", required=True)
    for key in ARM_KEYS:
        ap.add_argument("--board-" + key.replace("_", "-"), default="")
        ap.add_argument("--diag-" + key.replace("_", "-"), default="")
        ap.add_argument("--blind-" + key.replace("_", "-"), default="")
        ap.add_argument("--runner-summary-" + key.replace("_", "-"), default="")
    args = ap.parse_args()

    out = Path(args.out_dir)
    if out.exists():
        print("ERROR: --out-dir already exists: %s" % out, file=sys.stderr)
        sys.exit(2)
    out.mkdir(parents=True)

    frames = parse_npu_ab_manifest(Path(args.input_package) / "manifest.tsv")
    n = len(frames)

    arms = {}
    for key in ARM_KEYS:
        arms[key] = {
            "board": load_production(getattr(args, "board_" + key)),
            "diag": load_diagnostic(getattr(args, "diag_" + key)),
            "blind": load_blind(getattr(args, "blind_" + key)),
            "runner_summary": getattr(args, "runner_summary_" + key),
        }

    per = build_per_frame(frames, arms)

    # ---- 各臂汇总 ----
    arm_summary = {}
    for key in ARM_KEYS:
        arm_summary[key] = {
            "production": production_metrics(per, key),
            "diagnostic": diagnostic_metrics(per, key),
            "blind": blind_metrics(per, key),
            "pending": {
                "production": not bool(arms[key]["board"]),
                "diagnostic": not bool(arms[key]["diag"]),
                "blind": not bool(arms[key]["blind"]),
            },
        }

    # ---- 诊断旁路补回多少 (production ∪ diagnostic 的覆盖率/准确率) ----
    for key in ARM_KEYS:
        prod = arm_summary[key]["production"]
        diag = arm_summary[key]["diagnostic"]
        # 生产 gated 且正确, 或诊断旁路分类正确
        combined_correct = 0
        for r in per:
            if r[key + "_present"] and r[key + "_gated"] == 1 and \
                    r[key + "_pred"] == r["label"]:
                combined_correct += 1
            elif r[key + "_diag_present"] and r[key + "_diag_label_correct"] == 1:
                combined_correct += 1
        # 至少生产门或诊断旁路覆盖 (同一帧只算一次)
        covered = 0
        for r in per:
            if (r[key + "_present"] and r[key + "_gated"] == 1) or \
                    r[key + "_diag_present"]:
                covered += 1
        arm_summary[key]["combined"] = {
            "gated_or_diagnostic_covered": covered,
            "gated_or_diagnostic_correct": combined_correct,
            "accuracy": (combined_correct / covered) if covered else float("nan"),
            "diagnostic_recovered": diag["correct"],
        }

    # ---- runner summary 的六项统计 (权威; refused/apply_failed 不在诊断 TSV) ----
    for key in ARM_KEYS:
        rsp = arms[key]["runner_summary"]
        six = {k: None for k in SIX_STAT_KEYS}
        six["diagnostic_bypass_apply_failed"] = None
        if rsp and Path(rsp).exists():
            try:
                js = json.loads(Path(rsp).read_text(encoding="utf-8"))
                for k in SIX_STAT_KEYS + ["diagnostic_bypass_apply_failed"]:
                    if k in js:
                        six[k] = js[k]
            except Exception as e:  # noqa: BLE001
                six["_error"] = str(e)
        arm_summary[key]["six_statistics"] = six

    summary = {
        "token": "M29-RML24-FIX10CLASS24-CLASSIFICATION-GATE-SEPARATION1-JUDGED",
        "frames": n,
        "arms": arm_summary,
        "note": ("arm production=gated classification (0.100 fidelity gate unchanged); "
                 "arm diagnostic=Part B --diagnostic-force-classify bypass "
                 "(0.10<residual<=0.30 + alignment/validity pass, SEPARATE TSV, "
                 "classification_layer=NPU_BF16_DIAGNOSTIC); "
                 "arm blind=Part A no-fidelity-gate classification "
                 "(training residual NA); gate-reject=end-to-end fail; "
                 "hard_invalid never forced; missing input=PENDING; "
                 "diagnostic_bypass_refused/apply_failed are runner-summary-only "
                 "(not in diagnostic TSV)"),
    }
    with open(out / "judge_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    # ---- 每臂诊断混淆矩阵 + 生产端到端逐类 ----
    for key in ARM_KEYS:
        conf = np.zeros((C.N_CLASSES, C.N_CLASSES), dtype=np.int64)
        for r in per:
            if r[key + "_diag_pred"] is not None:
                conf[r["label"], r[key + "_diag_pred"]] += 1
        with open(out / ("confusion_%s_diagnostic.tsv" % key), "w",
                  encoding="utf-8") as f:
            f.write("true_class\t" + "\t".join(C.LABEL_ORDER_24) + "\n")
            for i in range(C.N_CLASSES):
                f.write(C.LABEL_ORDER_24[i] + "\t" +
                        "\t".join(str(conf[i, j]) for j in range(C.N_CLASSES)) + "\n")

    def fmt(x):
        return ("%.4f" % x) if (isinstance(x, float) and x == x) else "PENDING"

    # ---- stdout 摘要 ----
    print("RADIOML_GATE_SEPARATION_JUDGE frames=%d out_dir=%s" % (n, out))
    for key in ARM_KEYS:
        p = arm_summary[key]["production"]
        d = arm_summary[key]["diagnostic"]
        b = arm_summary[key]["blind"]
        cb = arm_summary[key]["combined"]
        print("  arm=%-14s prod_present=%d prod_gated=%d prod_gated_acc=%s "
              "prod_e2e=%s diag_total=%d diag_classified=%d diag_correct=%d "
              "diag_acc=%s blind_present=%d blind_acc=%s combined_acc=%s "
              "diag_recovered=%d" %
              (key, p["present"], p["gated"], fmt(p["gated_accuracy"]),
               fmt(p["end_to_end_gate_reject_is_fail"]), d["present"],
               d["classified"], d["correct"], fmt(d["accuracy"]), b["present"],
               fmt(b["accuracy"]), fmt(cb["accuracy"]), cb["diagnostic_recovered"]))
    print("RADIOML_GATE_SEPARATION_JUDGE_DONE")


if __name__ == "__main__":
    main()
