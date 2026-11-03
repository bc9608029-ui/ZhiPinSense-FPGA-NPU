#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
digital_roundtrip_radioml_dc.py -- 数字无 RF 回环 (dc-ab1 数字验证, 24 帧)。

对 short24 的每一帧, 同时跑 direct 与 dc-transport 两条数字理想回环, 并送入冻结 BF16
模型推理, 报告:
  * 数值误差 (corr / nMSE / 量化 RMS 误差 / finiteness / 裁剪) —— direct 与 dc 各一份;
  * 逐帧预测一致 (original 参考 == arm A host_pred; direct roundtrip vs original;
    dc roundtrip vs original / vs direct)。**corr/nMSE 很小不能替代预测一致**。

诚实边界 (不伪造):
  * 这里只实现**数字域**理想回环 = CI16 量化 + RMS 缩放 (direct) 或去 DC + CI16 + 尺度
    还原 + DC 加回 (dc-transport) 的确定性往返。
  * 生产恢复 (广线性 / coarse-CFO / 分数定时 / payload 增益) 在数字无 RF 情形下退化为
    恒等, 本脚本**不**用 Python 重实现该 C++ 恢复并声称等价。
  * original 参考 = npu-ab1 manifest 的 host_pred (arm A Host BF16 原始输入预测), 本脚本
    仍重新跑 original 输入以自检 icraft-run 调用逐字复现 arm A (pred == host_pred 全 24)。

用法:
    python -I scripts/digital_roundtrip_radioml_dc.py \
        --input-package <npu-ab1 input_package dir> \
        --icraft-run D:/icraft/bin/icraft-run.exe \
        --model-dir <npu-ab1 model_rml24_bf16 dir> \
        --out-dir <fresh dir>
输出 (out-dir 必须不存在):
    <sid>.direct.recovered.bin / <sid>.dc.recovered.bin   [2,1024] f32
    digital_roundtrip_dc.tsv          每帧数值证据 (direct/dc corr/nmse/quant_err/clip)
    digital_predictions_dc.tsv        逐帧预测一致 (original/direct/dc)
    digital_roundtrip_dc_summary.json
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_dualsdr_common as C  # noqa: E402
import radioml_dc_adapt as DC  # noqa: E402
from export_radioml_dualsdr_tx_payload import parse_npu_ab_manifest  # noqa: E402

NETWORK_NAME = "model_24class"

RESULT_HEADER = [
    "selection_id", "hdf5_row_index", "raw24_class", "modulation",
    "dataset_snr_db", "model_input_sha256",
    "direct_corr", "direct_nmse", "direct_quant_rms_err",
    "dc_corr", "dc_nmse", "dc_quant_rms_err",
    "direct_recovered_sha256", "dc_recovered_sha256",
    "clip_pre", "clip_post", "finite",
]

PRED_HEADER = [
    "selection_id", "raw24_class", "modulation",
    "original_pred", "direct_pred", "dc_pred",
    "original_correct", "direct_correct", "dc_correct",
    "direct_agrees_original", "dc_agrees_original", "dc_agrees_direct",
]


def run_host_infer(icraft_run: Path, model_json: Path, model_raw: Path,
                   input_bin: Path) -> tuple[int, bool]:
    """icraft-run Host BF16 -> (argmax, finite). 逐字复用 dualsdr 数字回环机制。"""
    with tempfile.TemporaryDirectory(prefix="rml24dc_") as td:
        workdir = Path(td)
        log_path = workdir / "logs"
        cmd = [str(icraft_run),
               "--json", str(model_json),
               "--raw", str(model_raw),
               "--network", NETWORK_NAME,
               "--input", str(input_bin),
               "--backends", "Host",
               "--dump_output",
               "--log_path", str(log_path)]
        proc = subprocess.run(cmd, cwd=str(workdir), capture_output=True)
        if proc.returncode != 0:
            raise RuntimeError("icraft-run failed: %s" %
                               proc.stderr.decode("utf-8", "replace")[-500:])
        ftmp_dir = log_path / NETWORK_NAME / "ftmpHQB"
        ftmps = list(ftmp_dir.glob("*.ftmp")) if ftmp_dir.is_dir() else []
        if len(ftmps) != 1:
            raise RuntimeError("expected exactly 1 ftmp, got %d" % len(ftmps))
        logits = np.fromfile(ftmps[0], dtype="<f4")
        assert logits.size == C.N_CLASSES
        finite = bool(np.all(np.isfinite(logits)))
        return (int(np.argmax(logits)) if finite else -1), finite


def roundtrip_evidence(original_iq: np.ndarray):
    """direct 与 dc 数字理想往返, 返回各自的 (recovered, corr, nmse, quant_err)。"""
    # direct
    r_direct, ev_direct = DC.direct_ideal_roundtrip(original_iq)
    corr_d = C.complex_corr(original_iq, r_direct)
    nmse_d = C.complex_nmse(original_iq, r_direct)
    quant_d = float(np.sqrt(np.mean(np.abs(original_iq - r_direct) ** 2)))
    # dc-transport
    r_dc, fwd = DC.dc_ideal_roundtrip(original_iq)
    corr_c = C.complex_corr(original_iq, r_dc)
    nmse_c = C.complex_nmse(original_iq, r_dc)
    quant_c = float(np.sqrt(np.mean(np.abs(original_iq - r_dc) ** 2)))
    return {
        "direct": (r_direct, corr_d, nmse_d, quant_d),
        "dc": (r_dc, corr_c, nmse_c, quant_c),
        "clip_pre": fwd["clip_pre"],
        "clip_post": fwd["clip_post"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-package", required=True)
    ap.add_argument("--icraft-run", required=True)
    ap.add_argument("--model-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    src = Path(args.input_package)
    out = Path(args.out_dir)
    if out.exists():
        print("ERROR: --out-dir already exists (refuse overwrite): %s" % out,
              file=sys.stderr)
        sys.exit(2)
    out.mkdir(parents=True)

    model_json = Path(args.model_dir) / "rml24_adamrv11_bf16.json"
    model_raw = Path(args.model_dir) / "rml24_adamrv11_bf16.raw"
    if not model_json.is_file() or not model_raw.is_file():
        raise RuntimeError("model json/raw not found under %s" % args.model_dir)
    icraft = Path(args.icraft_run)
    if not icraft.is_file():
        raise RuntimeError("icraft-run not found: %s" % icraft)

    frames = C.short24_selection(parse_npu_ab_manifest(src / "manifest.tsv"))

    result_rows = []
    pred_rows = []
    original_agree = 0
    direct_agree_orig = 0
    dc_agree_orig = 0
    dc_agree_direct = 0
    direct_correct = 0
    dc_correct = 0
    for fr in frames:
        bin_path = src / fr["input_file"]
        raw = bin_path.read_bytes()
        assert C.sha256_bytes(raw) == fr["model_input_sha256"]
        iq = C.load_tensor_2x1024(bin_path)
        ev = roundtrip_evidence(iq)

        r_direct = ev["direct"][0]
        r_dc = ev["dc"][0]
        direct_bytes = C.tensor_to_bytes(r_direct)
        dc_bytes = C.tensor_to_bytes(r_dc)
        direct_sha = C.sha256_bytes(direct_bytes)
        dc_sha = C.sha256_bytes(dc_bytes)
        (out / ("%d.direct.recovered.bin" % fr["selection_id"])).write_bytes(direct_bytes)
        (out / ("%d.dc.recovered.bin" % fr["selection_id"])).write_bytes(dc_bytes)

        # 推理: original / direct / dc
        orig_bytes = raw
        orig_in = out / ("%d.original.bin" % fr["selection_id"])
        orig_in.write_bytes(orig_bytes)
        original_pred, _ = run_host_infer(icraft, model_json, model_raw, orig_in)
        direct_pred, direct_finite = run_host_infer(
            icraft, model_json, model_raw, out / ("%d.direct.recovered.bin" % fr["selection_id"]))
        dc_pred, dc_finite = run_host_infer(
            icraft, model_json, model_raw, out / ("%d.dc.recovered.bin" % fr["selection_id"]))

        # original 必须逐字复现 arm A host_pred (自检 icraft-run 调用正确)。
        assert original_pred == fr["host_pred"], (
            "original inference diverged from arm A host_pred for selection_id=%d "
            "(got %d, manifest %d)" % (fr["selection_id"], original_pred, fr["host_pred"]))

        label = fr["raw24_class"]
        finite = direct_finite and dc_finite and (original_pred >= 0)
        o_correct = original_pred == label
        d_correct = direct_pred == label
        c_correct = dc_pred == label
        d_agree_o = direct_pred == original_pred
        c_agree_o = dc_pred == original_pred
        c_agree_d = dc_pred == direct_pred
        if o_correct:
            original_agree += 1
        if d_agree_o:
            direct_agree_orig += 1
        if c_agree_o:
            dc_agree_orig += 1
        if c_agree_d:
            dc_agree_direct += 1
        if d_correct:
            direct_correct += 1
        if c_correct:
            dc_correct += 1

        result_rows.append([
            fr["selection_id"], fr["hdf5_row_index"], fr["raw24_class"],
            fr["modulation"], fr["dataset_snr_db"], fr["model_input_sha256"],
            "%.12f" % ev["direct"][1], "%.3e" % ev["direct"][2],
            "%.6e" % ev["direct"][3],
            "%.12f" % ev["dc"][1], "%.3e" % ev["dc"][2],
            "%.6e" % ev["dc"][3],
            direct_sha, dc_sha,
            1 if ev["clip_pre"] else 0, 1 if ev["clip_post"] else 0,
            1 if finite else 0,
        ])
        pred_rows.append([
            fr["selection_id"], label, fr["modulation"],
            original_pred, direct_pred, dc_pred,
            1 if o_correct else 0, 1 if d_correct else 0, 1 if c_correct else 0,
            1 if d_agree_o else 0, 1 if c_agree_o else 0, 1 if c_agree_d else 0,
        ])

    with open(out / "digital_roundtrip_dc.tsv", "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(RESULT_HEADER) + "\n")
        for r in result_rows:
            f.write("\t".join(str(v) for v in r) + "\n")
    with open(out / "digital_predictions_dc.tsv", "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(PRED_HEADER) + "\n")
        for r in pred_rows:
            f.write("\t".join(str(v) for v in r) + "\n")

    n = len(frames)
    summary = {
        "token": "M29-RML24-FIX10CLASS24-ORIGINAL-RADIOML-DC-AB1-DIGITAL-VERIFICATION",
        "frames": n,
        "recovery_assumption": "DIGITAL_IDENTITY_ASSUMED (wide-linear/CFO/timing 待板端验证)",
        "clip_pre": sum(r[14] for r in result_rows),
        "clip_post": sum(r[15] for r in result_rows),
        "non_finite": sum(0 if r[16] else 1 for r in result_rows),
        "corr_direct_min": float(min(r[6] for r in result_rows)),
        "corr_dc_min": float(min(r[9] for r in result_rows)),
        "nmse_direct_max": max(float(r[7]) for r in result_rows),
        "nmse_dc_max": max(float(r[10]) for r in result_rows),
        "prediction_agreement": {
            "original_reproduces_arm_a_host_pred": n,
            "original_correct": "%d/%d" % (original_agree, n),
            "direct_correct": "%d/%d" % (direct_correct, n),
            "dc_correct": "%d/%d" % (dc_correct, n),
            "direct_agrees_original": "%d/%d" % (direct_agree_orig, n),
            "dc_agrees_original": "%d/%d" % (dc_agree_orig, n),
            "dc_agrees_direct": "%d/%d" % (dc_agree_direct, n),
        },
    }
    with open(out / "digital_roundtrip_dc_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    print("RADIOML_DC_DIGITAL original_repro_armA=%d/%d direct_correct=%d/%d "
          "dc_correct=%d/%d direct_agrees_orig=%d/%d dc_agrees_orig=%d/%d "
          "dc_agrees_direct=%d/%d corr_direct_min=%.12f corr_dc_min=%.12f "
          "nmse_direct_max=%.3e nmse_dc_max=%.3e clip=%d/%d non_finite=%d out_dir=%s" %
          (n, n, direct_correct, n, dc_correct, n,
           direct_agree_orig, n, dc_agree_orig, n, dc_agree_direct, n,
           summary["corr_direct_min"], summary["corr_dc_min"],
           summary["nmse_direct_max"], summary["nmse_dc_max"],
           summary["clip_pre"], summary["clip_post"], summary["non_finite"], out))
    print("RADIOML_DC_DIGITAL_DONE")


if __name__ == "__main__":
    main()
