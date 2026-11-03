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
    summary = {
        "token": "M29-RML24-FIX10CLASS24-ORIGINAL-RADIOML-DUALSDR-AB1-DIGITAL-ROUNDTRIP",
        "frames": len(final_rows),
        "byte_identical": byte_ident,
        "corr_min": min(corrs), "corr_median": float(np.median(corrs)),
        "nmse_max": max(nmse),
        "recovery_assumption": "DIGITAL_IDENTITY_ASSUMED (wide-linear/CFO/timing 待板端验证)",
        "predictions_computed": bool(pred_by_id),
    }
    with open(out / "digital_roundtrip_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    print("RADIOML_DUALSDR_DIGITAL_ROUNDTRIP frames=%d byte_identical=%d/%d "
          "corr_median=%.9f nmse_max=%.3e predictions=%s out_dir=%s" %
          (len(final_rows), byte_ident, len(final_rows),
           summary["corr_median"], summary["nmse_max"],
           "yes" if pred_by_id else "no", out))
    print("RADIOML_DUALSDR_DIGITAL_ROUNDTRIP_DONE")


def run_host_bf16_predictions(frames, out_dir, icraft_run, model_dir):
    """用 icraft-run Host BF16 后端跑恢复输入, 返回 {selection_id: {pred,finite}}。

    机制与 predict_rml24_bf16_baseline.py 相同: 每样本在隔离 temp cwd 中运行
    icraft-run.exe, 解析 <log>/model_24class/ftmpHQB/922.ftmp (24 LE fp32 logits)。
    任一样本失败 -> 抛异常 (fail-closed, 不静默回填)。
    """
    import struct
    import subprocess
    import tempfile

    preds = {}
    for fr in frames:
        rec_path = out_dir / ("%d.recovered.bin" % fr["selection_id"])
        with tempfile.TemporaryDirectory() as tmp:
            run_cmd = [icraft_run, "--model", model_dir, "--input", str(rec_path),
                       "--backend", "Host", "--out", tmp]
            proc = subprocess.run(run_cmd, cwd=tmp, capture_output=True, text=True)
            if proc.returncode != 0:
                raise RuntimeError("icraft-run failed for %s: %s" %
                                   (fr["input_file"], proc.stderr[-500:]))
            logits_path = Path(tmp) / "model_24class" / "ftmpHQB" / "922.ftmp"
            if not logits_path.exists():
                raise RuntimeError("missing logits output for %s" % fr["input_file"])
            logits = np.fromfile(logits_path, dtype="<f4")
            assert logits.size == C.N_CLASSES
            finite = bool(np.all(np.isfinite(logits)))
            preds[fr["selection_id"]] = {
                "pred": int(np.argmax(logits)) if finite else -1,
                "finite": finite,
            }
    return preds


if __name__ == "__main__":
    main()
