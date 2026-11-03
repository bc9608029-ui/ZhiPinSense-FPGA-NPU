#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
digital_roundtrip_radioml_dualsdr.py -- Phase B: 数字无 RF 回环 (arm D 主机侧)。

对 480 帧原始 RadioML 输入, 执行:
    原始 [2,1024] f32  ->  循环铺排 53760  ->  CI16(RMS2048)  ->  理想接收(无 RF)
      ->  前 1024 复样本  ->  unscale  ->  [2,1024] f32 模型输入
逐帧记录 SHA / 复相关 / NMSE / 幅度变化 / 量化误差。

诚实边界 (不伪造):
  * 这里只实现**数字域**理想回环 = CI16 量化 + RMS 缩放的确定性往返。
  * 生产恢复 (广线性 IQ 平衡 / coarse-CFO / 分数定时 / payload 增益训练) 在数字
    无 RF 情形下退化为恒等 (CFO=0、定时精确、无模拟 IQ 不平衡、链路增益=1), 但本
    脚本**不**用 Python 重实现该 C++ 恢复并声称等价 —— 该部分标记为
    "DIGITAL_IDENTITY_ASSUMED; 板端恢复逐字执行, 待板端验证"。
  * arm D 的模型预测: 若提供 --icraft-run 与 --model-dir, 用与
    predict_rml24_bf16_baseline.py 相同的 Host BF16 后端跑恢复输入并写预测;
    否则写 N/A 并由判定器标记 PENDING。

输出 (out-dir 必须不存在):
    <selection_id>.recovered.bin    [2,1024] f32 数字回环模型输入
    digital_roundtrip.tsv          每帧证据 (SHA/相关/NMSE/幅度)
    digital_predictions.tsv        (若跑模型) Host BF16 arm-D 预测
    digital_roundtrip_summary.json
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
from export_radioml_dualsdr_tx_payload import (  # noqa: E402
    TX_MANIFEST_HEADER, parse_npu_ab_manifest)

RESULT_HEADER = [
    "selection_id", "hdf5_row_index", "raw24_class", "modulation",
    "dataset_snr_db", "model_input_sha256", "recovered_sha256",
    "byte_identical", "corr", "nmse", "amplitude_ratio",
    "quant_rms_error", "digital_pred", "digital_pred_finite",
]

DIGITAL_PRED_HEADER = [
    "selection_id", "raw24_class", "modulation", "dataset_snr_db",
    "digital_pred", "host_pred", "correct_raw24", "matches_host_pred",
]


def compute_consistency(frames, pred_by_id):
    """arm D 预测一致率: 总体 / 每SNR(0,10,20,30) / 每类 / 与 arm A host_pred 分歧。

    frames 来自 npu-ab1 8 列 manifest (含 host_pred = arm A Host BF16 参考预测)。
    返回 {summary:{...}, rows:[...]}。
    """
    rows = []
    correct = 0
    finite = 0
    diverge = 0
    per_snr = {s: {"n": 0, "correct": 0} for s in (0, 10, 20, 30)}
    per_class = {c: {"n": 0, "correct": 0} for c in range(C.N_CLASSES)}
    for fr in frames:
        sid = fr["selection_id"]
        p = pred_by_id[sid]
        pred = p["pred"]
        is_finite = p["finite"]
        raw24 = fr["raw24_class"]
        host_pred = fr["host_pred"]
        is_correct = is_finite and pred == raw24
        matches_host = is_finite and pred == host_pred
        if is_finite:
            finite += 1
        if is_correct:
            correct += 1
        if is_finite and pred != host_pred:
            diverge += 1
        per_snr[fr["dataset_snr_db"]]["n"] += 1
        if is_correct:
            per_snr[fr["dataset_snr_db"]]["correct"] += 1
        per_class[raw24]["n"] += 1
        if is_correct:
            per_class[raw24]["correct"] += 1
        rows.append([
            sid, raw24, fr["modulation"], fr["dataset_snr_db"],
            pred if is_finite else -1, host_pred,
            1 if is_correct else 0, 1 if matches_host else 0,
        ])
    n = len(frames)
    return {
        "rows": rows,
        "summary": {
            "frames": n,
            "correct": correct,
            "finite": finite,
            "diverge_vs_arm_a": diverge,
            "per_snr": {str(s): "%d/%d" % (per_snr[s]["correct"], per_snr[s]["n"])
                        for s in (0, 10, 20, 30)},
            "per_class": {
                C.LABEL_ORDER_24[c]: "%d/%d" % (per_class[c]["correct"], per_class[c]["n"])
                for c in range(C.N_CLASSES)},
        },
    }


def ideal_receive(original_iq: np.ndarray):
    """数字理想回环往返。返回 (recovered_iq, corr, nmse, amp_ratio, quant_err)。"""
    rms = C.native_rms(original_iq)
    scale = C.tx_scale_from_rms(rms, C.RF_TARGET_RMS)
    tiled = C.cyclic_tile_1024_to_payload(original_iq)
    ci16 = C.quantize_ci16(tiled, scale)
    counts = C.deinterleave_int16(ci16)          # 53760 复 counts (理想接收)
    window = counts[:C.MODEL_SAMPLES]            # 模型窗口 = 前 1024
    unscale = rms / C.RF_TARGET_RMS
    recovered = window * unscale                 # counts -> 原 f32 域
    corr = C.complex_corr(original_iq, recovered)
    nmse = C.complex_nmse(original_iq, recovered)
    amp_ratio = C.native_rms(recovered) / rms if rms > 0 else float("nan")
    quant_err = float(np.sqrt(np.mean(np.abs(original_iq - recovered) ** 2)))
    return recovered, corr, nmse, amp_ratio, quant_err


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-package", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--icraft-run", default="")
    ap.add_argument("--model-dir", default="")
    args = ap.parse_args()

    src = Path(args.input_package)
    out = Path(args.out_dir)
    if out.exists():
        print("ERROR: --out-dir already exists (refuse overwrite): %s" % out, file=sys.stderr)
        sys.exit(2)
    out.mkdir(parents=True)

    frames = parse_npu_ab_manifest(src / "manifest.tsv")

    rows = []
    for fr in frames:
        bin_path = src / fr["input_file"]
        raw = bin_path.read_bytes()
        assert C.sha256_bytes(raw) == fr["model_input_sha256"]
        iq = C.load_tensor_2x1024(bin_path)
        recovered, corr, nmse, amp_ratio, quant_err = ideal_receive(iq)
        rec_bytes = C.tensor_to_bytes(recovered)
        rec_sha = C.sha256_bytes(rec_bytes)
        (out / ("%d.recovered.bin" % fr["selection_id"])).write_bytes(rec_bytes)
        rows.append([
            fr["selection_id"], fr["hdf5_row_index"], fr["raw24_class"],
            fr["modulation"], fr["dataset_snr_db"], fr["model_input_sha256"],
            rec_sha, 1 if rec_sha == fr["model_input_sha256"] else 0,
            "%.12f" % corr, "%.3e" % nmse, "%.9f" % amp_ratio,
            "%.6e" % quant_err, "", "",
        ])

    # 数字回环预测 (可选, Host BF16, 与 predict_rml24_bf16_baseline.py 同一机制)
    pred_by_id = {}
    if args.icraft_run and args.model_dir:
        pred_by_id = run_host_bf16_predictions(frames, out, args.icraft_run, args.model_dir)

    # 回填预测列
    final_rows = []
    for r in rows:
        sid = r[0]
        p = pred_by_id.get(sid)
        if p is not None:
            r[12] = p["pred"]
            r[13] = 1 if p["finite"] else 0
        final_rows.append(r)

    with open(out / "digital_roundtrip.tsv", "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(RESULT_HEADER) + "\n")
        for r in final_rows:
            f.write("\t".join(str(v) for v in r) + "\n")

    byte_ident = sum(1 for r in final_rows if r[7] == 1)
    corrs = [float(r[8]) for r in final_rows]
    nmse = [float(r[9]) for r in final_rows]

    # arm D 预测一致率 (总体 / 每SNR / 每类 / 与 arm A host_pred 的分歧)
    consistency = None
    if pred_by_id:
        consistency = compute_consistency(frames, pred_by_id)
        with open(out / "digital_predictions.tsv", "w", encoding="utf-8", newline="") as f:
            f.write("\t".join(DIGITAL_PRED_HEADER) + "\n")
            for p in consistency["rows"]:
                f.write("\t".join(str(v) for v in p) + "\n")

    summary = {
        "token": "M29-RML24-FIX10CLASS24-ORIGINAL-RADIOML-DUALSDR-AB1-DIGITAL-ROUNDTRIP",
        "frames": len(final_rows),
        "byte_identical": byte_ident,
        "corr_min": min(corrs), "corr_median": float(np.median(corrs)),
        "nmse_max": max(nmse),
        "recovery_assumption": "DIGITAL_IDENTITY_ASSUMED (wide-linear/CFO/timing 待板端验证)",
        "predictions_computed": bool(pred_by_id),
        "prediction_consistency": consistency["summary"] if consistency else None,
    }
    with open(out / "digital_roundtrip_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    if consistency:
        s = consistency["summary"]
        print("RADIOML_DUALSDR_DIGITAL_ARM_D overall=%d/%d per_snr={0:%s,10:%s,20:%s,30:%s} "
              "diverge_vs_armA=%d" %
              (s["correct"], s["frames"],
               s["per_snr"]["0"], s["per_snr"]["10"], s["per_snr"]["20"],
               s["per_snr"]["30"], s["diverge_vs_arm_a"]))

    print("RADIOML_DUALSDR_DIGITAL_ROUNDTRIP frames=%d byte_identical=%d/%d "
          "corr_median=%.9f nmse_max=%.3e predictions=%s out_dir=%s" %
          (len(final_rows), byte_ident, len(final_rows),
           summary["corr_median"], summary["nmse_max"],
           "yes" if pred_by_id else "no", out))
    print("RADIOML_DUALSDR_DIGITAL_ROUNDTRIP_DONE")


NETWORK_NAME = "model_24class"


def run_host_bf16_predictions(frames, out_dir, icraft_run, model_dir):
    """用 icraft-run Host BF16 后端跑恢复输入, 返回 {selection_id: {pred,finite}}。

    机制与 predict_rml24_bf16_baseline.py 相同 (逐字): 每样本在隔离 temp cwd 中运行
      icraft-run --json <json> --raw <raw> --network model_24class --input <bin>
                 --backends Host --dump_output --log_path <log>
    解析 <log>/model_24class/ftmpHQB/*.ftmp (恰 1 个, 24 LE fp32 logits)。
    任一样本失败 -> 抛异常 (fail-closed, 不静默回填)。
    """
    import subprocess
    import tempfile

    model_json = Path(model_dir) / "rml24_adamrv11_bf16.json"
    model_raw = Path(model_dir) / "rml24_adamrv11_bf16.raw"
    if not model_json.is_file() or not model_raw.is_file():
        raise RuntimeError("model json/raw not found under %s" % model_dir)

    preds = {}
    for fr in frames:
        rec_path = out_dir / ("%d.recovered.bin" % fr["selection_id"])
        with tempfile.TemporaryDirectory(prefix="rml24dsab_") as td:
            tmp = Path(td)
            log_path = tmp / "logs"
            run_cmd = [icraft_run,
                       "--json", str(model_json),
                       "--raw", str(model_raw),
                       "--network", NETWORK_NAME,
                       "--input", str(rec_path),
                       "--backends", "Host",
                       "--dump_output",
                       "--log_path", str(log_path)]
            proc = subprocess.run(run_cmd, cwd=td, capture_output=True)
            if proc.returncode != 0:
                raise RuntimeError("icraft-run failed for %s: %s" %
                                   (fr["input_file"],
                                    proc.stderr.decode("utf-8", "replace")[-500:]))
            ftmp_dir = log_path / NETWORK_NAME / "ftmpHQB"
            ftmps = list(ftmp_dir.glob("*.ftmp")) if ftmp_dir.is_dir() else []
            if len(ftmps) != 1:
                raise RuntimeError("expected exactly 1 ftmp under %s, got %d (frame %s)"
                                   % (ftmp_dir, len(ftmps), fr["input_file"]))
            logits = np.fromfile(ftmps[0], dtype="<f4")
            assert logits.size == C.N_CLASSES
            finite = bool(np.all(np.isfinite(logits)))
            preds[fr["selection_id"]] = {
                "pred": int(np.argmax(logits)) if finite else -1,
                "finite": finite,
            }
    return preds


if __name__ == "__main__":
    main()
