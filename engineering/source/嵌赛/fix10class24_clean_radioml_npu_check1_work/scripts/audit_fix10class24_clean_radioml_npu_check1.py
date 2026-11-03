#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
audit_fix10class24_clean_radioml_npu_check1.py

fix10class24-clean-radioml-npu-check1 板端结果 fail-closed 独立判读。

不信任 GATE_RESULT result=PASS：本脚本从逐样本结果
    <out-dir>/route_f_fix10class24_bf16_clean_iq_results.tsv
独立重算 scored / excluded / label_correct / baseline_agreement /
repeat_deterministic / nan_or_inf，并把逐样本行与冻结 manifest
（clean24_smoke/route_d2_rf_manifest.tsv）与冻结 baseline
（baselines/clean24_smoke_raw24_bf16_baseline.tsv）做身份交叉校验。

被排除样本仍计入 24 的分母：scored + excluded 必须 == 24。
"23/23" 式谎报（把 excluded 从分母删掉）会被硬门禁拒绝。

用法（Windows: python；板端结果目录 --out-dir 由用户从板端回传）:
  python audit_fix10class24_clean_radioml_npu_check1.py \
      --out-dir    <board 输出目录(含 *_clean_iq_results.tsv 与 summary.json)> \
      --frozen-dir <clean24_smoke 目录(含 route_d2_rf_manifest.tsv)> \
      --baseline   <baselines/clean24_smoke_raw24_bf16_baseline.tsv>

退出码:
  0  = 全部硬门禁(身份/完整/确定性)通过；label_correct<24 是合法测量结果(打印 ERRORS)。
  1  = 硬门禁失败(身份不符 / 24 行不足 / 类别覆盖不全 / baseline 篡改 / 分母丢弃 /
       NaN/Inf / 两次推理不一致 / summary.json 与逐样本不一致)。
纯 stdlib，无第三方依赖。
"""
import argparse
import json
import os
import sys

# 冻结身份常量（fix10class24-clean-radioml-npu-check1 任务书逐字值）。
FROZEN_MODEL_JSON_SHA = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
FROZEN_MODEL_RAW_SHA = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"
EXPECTED_SOURCE_INDEXES = [i * 500 for i in range(24)]  # 0,500,...,11500
EXPECTED_SOURCE_INDEX_SET = set(EXPECTED_SOURCE_INDEXES)
EXPECTED_RAW24_CLASSES = set(range(24))  # 0..23
N_CLASSES = 24
RESULTS_TSV_NAME = "route_f_fix10class24_bf16_clean_iq_results.tsv"
SUMMARY_JSON_NAME = "route_f_fix10class24_bf16_clean_iq_summary.json"
VERDICT_SCORED = "CLEAN_DIGITAL_SCORED"
VERDICT_EXCLUDED = "CLEAN_NO_VALID_WINDOW"


def _fatal(msg):
    sys.stderr.write("AUDIT_FATAL: %s\n" % msg)
    sys.exit(1)


def _read_lines_utf8(path):
    with open(path, "r", encoding="utf-8") as f:
        return [ln.rstrip("\r\n") for ln in f]


def load_manifest(frozen_dir):
    """manifest → dict[source_index] = (raw24_class, modulation, split_role)。"""
    path = os.path.join(frozen_dir, "route_d2_rf_manifest.tsv")
    if not os.path.isfile(path):
        _fatal("manifest 缺失: %s" % path)
    lines = _read_lines_utf8(path)
    header = lines[0].split("\t")
    assert header[1] == "source_index" and header[2] == "raw24_class", header
    out = {}
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        sid = int(f[1])
        cls = int(f[2])
        mod = f[4]
        role = f[6]
        if sid in out:
            _fatal("manifest source_index 重复: %d" % sid)
        out[sid] = (cls, mod, role)
    if set(out) != EXPECTED_SOURCE_INDEX_SET:
        _fatal("manifest source_index 集合 != {0..11500 step 500}: %d 行" % len(out))
    if {c for c, _, _ in out.values()} != EXPECTED_RAW24_CLASSES:
        _fatal("manifest raw24_class 未覆盖 0..23")
    return out


def load_baseline(baseline_path):
    """baseline → dict[source_index] = (frozen_bf16_raw24_pred, model_sha256)。"""
    if not os.path.isfile(baseline_path):
        _fatal("baseline 缺失: %s" % baseline_path)
    lines = _read_lines_utf8(baseline_path)
    header = lines[0].split("\t")
    assert header[0] == "source_index" and header[5] == "frozen_bf16_raw24_pred", header
    out = {}
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        sid = int(f[0])
        pred = int(f[5])
        msha = f[6]
        out[sid] = (pred, msha)
    if set(out) != EXPECTED_SOURCE_INDEX_SET:
        _fatal("baseline source_index 集合 != 24 行")
    for sid, (pred, msha) in out.items():
        if msha != FROZEN_MODEL_JSON_SHA:
            _fatal("baseline source_index=%d model_sha256 不符: %s" % (sid, msha))
        if not (0 <= pred < N_CLASSES):
            _fatal("baseline source_index=%d 非法 pred=%d" % (sid, pred))
    return out


def load_results(out_dir):
    """results TSV → (scored_rows, excluded_rows)，逐行 16 列。"""
    path = os.path.join(out_dir, RESULTS_TSV_NAME)
    if not os.path.isfile(path):
        _fatal("逐样本结果缺失: %s" % path)
    lines = _read_lines_utf8(path)
    header = lines[0].split("\t")
    expected = ["file_name", "source_index", "raw24_class", "modulation", "snr_db",
                "split_role", "valid", "raw24_pred", "baseline_pred", "correct",
                "prediction_agreement", "repeat_deterministic", "window_corr",
                "window_nmse", "delay_offset", "verdict"]
    if header != expected:
        _fatal("results 表头不符:\n got=%r\n exp=%r" % (header, expected))
    scored, excluded = [], []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        if len(f) != 16:
            _fatal("results 行字段数 != 16: %r" % ln)
        row = {
            "file_name": f[0],
            "source_index": int(f[1]),
            "raw24_class": int(f[2]),
            "modulation": f[3],
            "snr_db": f[4],
            "split_role": f[5],
            "valid": int(f[6]),
            "raw24_pred": int(f[7]),
            "baseline_pred": int(f[8]),
            "correct": int(f[9]),
            "prediction_agreement": int(f[10]),
            "repeat_deterministic": int(f[11]),
            "window_corr": f[12],
            "window_nmse": f[13],
            "delay_offset": f[14],
            "verdict": f[15],
        }
        if row["verdict"] == VERDICT_SCORED:
            scored.append(row)
        elif row["verdict"] == VERDICT_EXCLUDED:
            excluded.append(row)
        else:
            _fatal("未知 verdict: %r" % row["verdict"])
    return scored, excluded


def load_summary(out_dir):
    """summary.json 可选；缺失返回 None（仍用逐样本独立重算）。"""
    path = os.path.join(out_dir, SUMMARY_JSON_NAME)
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _as_int(x):
    return int(x) if str(x).lstrip("-").isdigit() else x


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--frozen-dir", required=True)
    ap.add_argument("--baseline", required=True)
    args = ap.parse_args()

    manifest = load_manifest(args.frozen_dir)
    baseline = load_baseline(args.baseline)
    scored, excluded = load_results(args.out_dir)
    summary = load_summary(args.out_dir)

    problems = []
    info = {}

    # ---- 逐样本硬门禁（身份/完整/确定性） ----
    total_rows = len(scored) + len(excluded)
    if total_rows != N_CLASSES:
        problems.append("总行数=%d != 24（excluded 不得从 24 分母剔除）" % total_rows)
    if len(set(r["source_index"] for r in scored + excluded)) != total_rows:
        problems.append("source_index 有重复")

    sid_set = {r["source_index"] for r in scored + excluded}
    if sid_set != EXPECTED_SOURCE_INDEX_SET:
        problems.append("source_index 集合 != {0..11500 step 500}（缺/多: %s）" %
                        sorted(EXPECTED_SOURCE_INDEX_SET ^ sid_set))

    covered_classes = set()
    for r in scored + excluded:
        cls, mod, role = manifest.get(r["source_index"], (None, None, None))
        if cls is None:
            problems.append("source_index=%d 不在 manifest" % r["source_index"])
            continue
        covered_classes.add(cls)
        if cls != r["raw24_class"]:
            problems.append("source_index=%d raw24_class=%d != manifest=%d" %
                            (r["source_index"], r["raw24_class"], cls))
        if mod != r["modulation"]:
            problems.append("source_index=%d modulation 不符 %r != %r" %
                            (r["source_index"], r["modulation"], mod))
    if covered_classes != EXPECTED_RAW24_CLASSES:
        problems.append("raw24_class 未覆盖 0..23（缺 %s）" %
                        sorted(EXPECTED_RAW24_CLASSES - covered_classes))

    # ---- baseline 身份交叉校验（防止 baseline 被替换） ----
    for r in scored:
        bpred, _ = baseline[r["source_index"]]
        if r["baseline_pred"] != bpred:
            problems.append("source_index=%d 结果 baseline_pred=%d != 冻结=%d" %
                            (r["source_index"], r["baseline_pred"], bpred))

    # ---- 指标独立重算（从逐样本，不读 summary.json 的数值） ----
    nan_or_inf = sum(1 for r in scored if r["valid"] == 0)
    repeat_det = sum(1 for r in scored if r["repeat_deterministic"] == 1)
    label_correct = sum(1 for r in scored if r["correct"] == 1)
    baseline_agreement = sum(1 for r in scored if r["prediction_agreement"] == 1)

    # 独立重校验 correct/prediction_agreement/repeat_deterministic 的字段自洽。
    for r in scored:
        exp_correct = 1 if (r["valid"] == 1 and r["raw24_pred"] == r["raw24_class"]) else 0
        if r["correct"] != exp_correct:
            problems.append("source_index=%d correct 字段不自洽(%d vs %d)" %
                            (r["source_index"], r["correct"], exp_correct))
        bpred, _ = baseline[r["source_index"]]
        exp_agr = 1 if (r["valid"] == 1 and r["raw24_pred"] == bpred) else 0
        if r["prediction_agreement"] != exp_agr:
            problems.append("source_index=%d prediction_agreement 不自洽" %
                            r["source_index"])

    # ---- summary.json 交叉校验（若存在） ----
    if summary is not None:
        for k in ("model_sha", "input_kind", "holdout_files", "baseline_identity_ok",
                  "scored", "excluded", "nan_or_inf", "repeat_deterministic",
                  "baseline_rows"):
            if k not in summary:
                problems.append("summary.json 缺字段 %s" % k)
        if summary.get("model_sha") != FROZEN_MODEL_RAW_SHA:
            problems.append("summary.json model_sha=%r != 冻结 raw %s" %
                            (summary.get("model_sha"), FROZEN_MODEL_RAW_SHA))
        if summary.get("input_kind") != "radioml-d2-2p56m":
            problems.append("summary.json input_kind=%r != radioml-d2-2p56m" %
                            summary.get("input_kind"))
        if summary.get("holdout_files") != N_CLASSES:
            problems.append("summary.json holdout_files=%r != 24" %
                            summary.get("holdout_files"))
        if summary.get("baseline_identity_ok") is not True:
            problems.append("summary.json baseline_identity_ok != true")
        for k in ("scored", "excluded", "nan_or_inf", "repeat_deterministic"):
            if k in summary:
                info["summary_%s" % k] = summary[k]
        if summary.get("scored") != len(scored):
            problems.append("summary.json scored=%r != 逐样本=%d" %
                            (summary.get("scored"), len(scored)))
        if summary.get("excluded") != len(excluded):
            problems.append("summary.json excluded=%r != 逐样本=%d" %
                            (summary.get("excluded"), len(excluded)))
        if summary.get("nan_or_inf") != nan_or_inf:
            problems.append("summary.json nan_or_inf=%r != 逐样本=%d" %
                            (summary.get("nan_or_inf"), nan_or_inf))
        if summary.get("repeat_deterministic") != repeat_det:
            problems.append("summary.json repeat_deterministic=%r != 逐样本=%d" %
                            (summary.get("repeat_deterministic"), repeat_det))
    else:
        info["summary_present"] = False

    # ---- 确定性/有限性硬门禁（任何一次不满足即测量无效） ----
    if nan_or_inf != 0:
        problems.append("nan_or_inf=%d > 0（有限性被破坏，测量无效）" % nan_or_inf)
    # 确定性只能在 scored 样本上测量（excluded 未进入推理，不算 0）。
    if repeat_det != len(scored):
        problems.append("repeat_deterministic=%d != scored=%d（两次推理不一致，测量无效）"
                        % (repeat_det, len(scored)))

    # ---- 错误明细 ----
    errors = [r for r in scored if r["correct"] == 0]
    excluded_detail = [r for r in excluded]

    # ---- 报告 ----
    print("=" * 72)
    print("fix10class24-clean-radioml-npu-check1 逐样本独立判读")
    print("=" * 72)
    print("模型 JSON SHA: %s" % FROZEN_MODEL_JSON_SHA)
    print("模型 RAW  SHA: %s" % FROZEN_MODEL_RAW_SHA)
    print("总行数 = %d (scored %d + excluded %d)" %
          (total_rows, len(scored), len(excluded)))
    print("source_index 覆盖: %s" %
          ("OK (0,500,...,11500 共24)" if sid_set == EXPECTED_SOURCE_INDEX_SET else "FAIL"))
    print("raw24_class 覆盖: %s" %
          ("OK (0..23)" if covered_classes == EXPECTED_RAW24_CLASSES else "FAIL"))
    print("scored          = %d" % len(scored))
    print("excluded        = %d" % len(excluded))
    print("label_correct   = %d / 24" % label_correct)
    print("baseline_agree  = %d / 24   (与 Host 基线一致数)" % baseline_agreement)
    print("repeat_det      = %d / %d   (两次推理预测一致数 / scored)"
          % (repeat_det, len(scored)))
    print("nan_or_inf      = %d" % nan_or_inf)
    print("-" * 72)
    if errors:
        print("错误样本（%d 个）:" % len(errors))
        for r in errors:
            print("  source_index=%-6d true=%-2d pred=%-2d  %s  corr=%s nmse=%s" %
                  (r["source_index"], r["raw24_class"], r["raw24_pred"],
                   r["modulation"], r["window_corr"], r["window_nmse"]))
    else:
        print("错误样本: 无（24/24）")
    if excluded_detail:
        print("未能进入分类（%d 个）:" % len(excluded_detail))
        for r in excluded_detail:
            print("  source_index=%-6d %-12s verdict=%s corr=%s nmse=%s delay=%s" %
                  (r["source_index"], r["modulation"], r["verdict"],
                   r["window_corr"], r["window_nmse"], r["delay_offset"]))
    else:
        print("未能进入分类: 无")
    print("-" * 72)
    print("对照表:")
    print("  | 证据 | 结果 |")
    print("  |---|---|---|")
    print("  | 既有纯净 RadioML Host BF16 | 24/24 |")
    print("  | 本次纯净 RadioML 板端 NPU   | %d/24（scored %d / excluded %d）|" %
          (label_correct, len(scored), len(excluded)))
    print("  | 既有双 SDR RMS2048 诊断合并 | 19/24（板端过门 + Host 门拒强制）|")
    print("  |   （末行证据层级不同，非纯板端 NPU 对照） |")
    print("=" * 72)

    if problems:
        print("硬门禁失败（%d 项）:" % len(problems))
        for p in problems:
            print("  - %s" % p)
        _fatal("硬门禁未通过，判读失败")
    else:
        print("硬门禁全部通过（身份/完整/确定性 OK）。")
        if errors:
            print("结论: 测量完成，存在 %d 个分类错误（定位板端数字链 vs Host 基线差异，"
                  "不直接归因 RF）。" % len(errors))
        else:
            print("结论: 24/24，这 24 个纯净样本在当前板端数字分类链上全部正确。")
        sys.exit(0)


if __name__ == "__main__":
    main()
