#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_radioml_dualsdr_tx_payload.py -- Phase A/B: 480 原始 RadioML 帧的 TX 派生
CI16 payload 导出 (fix10class24-original-radioml-dualsdr-ab1)。

把 npu-ab1 的 480 帧输入包 (manifest.tsv + 480 个 [2,1024] f32 .bin) 读入, 对每帧
应用**确定性、类无关**的传输适配, 生成生产 RF 链可发射的 CI16 payload (53760 复样本
循环铺排 + RMS2048 量化), 并逐帧记录 SHA / 幅度 / 缩放 / 裁剪证据。

关键契约 (Phase A 结论):
  * 原始输入是 [2,1024] f32 (训练契约逐字), 而生产 RF payload 冻结为 53760 复样本,
    二者不可直接兼容。本任务**不修改**生产恢复/训练帧/窗口规则, 而是:
      1) 循环铺排 1024 -> 53760 (确定性、保 RMS、类无关);
      2) 量化 f32 -> CI16 (scale = 2048/native_rms, llround+clamp, 与生产 TX 一致);
      3) 记录 unscale = native_rms/2048, 供恢复后模型窗口把 counts 映回原 f32 域;
      4) 模型窗口 = 恢复后 payload 的前 1024 个复样本。
  * dataset_snr_db 是数据集的标称 SNR, **不是**真实 RX SNR。

Red lines: 不改模型/训练/恢复/门限; 原始输入与 TX 派生输入分开存储; 不按类选择。

用法:
    python -I scripts/export_radioml_dualsdr_tx_payload.py \
        --input-package <npu-ab1 input_package dir> \
        --out-dir <fresh tx payload dir>
输出 (out-dir 必须不存在, 拒绝覆盖):
    <selection_id>.i16           107520 int16 = 53760 复 CI16 payload (交错 I0,Q0)
    tx_manifest.tsv              每帧 18 列 (主键 + TX 派生证据)
    SHA256SUMS.txt
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_dualsdr_common as C  # noqa: E402

# npu-ab1 输入包 manifest 的 8 列表头 (逐字, 权威)
NPU_AB_MANIFEST_HEADER = ("selection_id\thdf5_row_index\traw24_class\tmodulation\t"
                          "snr_db\tinput_file\tinput_sha256\thost_pred")

# 本任务 TX 派生 manifest 表头 (主键改名对齐任务书: snr_db->dataset_snr_db,
# input_sha256->model_input_sha256; 追加 TX 派生证据列)
TX_MANIFEST_HEADER = [
    "selection_id", "hdf5_row_index", "raw24_class", "modulation",
    "dataset_snr_db", "input_file", "model_input_sha256", "host_pred",
    "tx_payload_file", "tx_payload_sha256", "native_rms", "tx_scale",
    "unscale", "peak_pre", "peak_post", "clip_pre", "clip_post",
    "adaptation",
]


def parse_npu_ab_manifest(path: Path):
    """读 npu-ab1 480 帧 manifest, fail-closed 校验主键唯一/连续/范围。"""
    lines = path.read_text(encoding="utf-8").rstrip("\n").split("\n")
    assert lines[0].rstrip("\r") == NPU_AB_MANIFEST_HEADER, "manifest header mismatch"
    frames = []
    seen = set()
    for ln in lines[1:]:
        ln = ln.rstrip("\r")
        if not ln.strip():
            continue
        f = ln.split("\t")
        assert len(f) == 8, "manifest line not 8 columns: %r" % ln
        fr = {
            "selection_id": int(f[0]),
            "hdf5_row_index": int(f[1]),
            "raw24_class": int(f[2]),
            "modulation": f[3],
            "dataset_snr_db": int(f[4]),
            "input_file": f[5],
            "model_input_sha256": f[6],
            "host_pred": int(f[7]),
        }
        assert fr["selection_id"] == len(frames) + 1, "non-contiguous selection_id"
        assert 0 <= fr["raw24_class"] < C.N_CLASSES
        assert fr["dataset_snr_db"] in (0, 10, 20, 30)
        assert len(fr["model_input_sha256"]) == 64
        key = (fr["hdf5_row_index"], fr["input_file"], fr["model_input_sha256"])
        assert key not in seen, "duplicate identity %r" % (key,)
        seen.add(key)
        frames.append(fr)
    assert len(frames) == 480, "manifest has %d frames (want 480)" % len(frames)
    return frames


def build_tx_payload(original_iq: np.ndarray):
    """确定性 TX 适配: 1024 -> 53760 循环铺排 -> CI16(RMS2048)。返回证据字典。"""
    tiled = C.cyclic_tile_1024_to_payload(original_iq)
    rms = C.native_rms(original_iq)
    scale = C.tx_scale_from_rms(rms, C.RF_TARGET_RMS)
    ci16 = C.quantize_ci16(tiled, scale)
    peak_pre = float(np.abs(original_iq).max())
    peak_post = float(np.abs(ci16).max())
    return {
        "payload_i16": ci16,
        "native_rms": rms,
        "tx_scale": scale,
        "unscale": rms / C.RF_TARGET_RMS if scale > 0 else 0.0,
        "peak_pre": peak_pre,
        "peak_post": peak_post,
        "clip_pre": peak_pre >= 32767.0,
        "clip_post": peak_post >= 32767.0,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-package", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    src = Path(args.input_package)
    out = Path(args.out_dir)
    if out.exists():
        print("ERROR: --out-dir already exists (refuse overwrite): %s" % out, file=sys.stderr)
        sys.exit(2)
    out.mkdir(parents=True)

    frames = parse_npu_ab_manifest(src / "manifest.tsv")

    rows = []
    sha_lines = []
    clip_count = 0
    for fr in frames:
        bin_path = src / fr["input_file"]
        raw = bin_path.read_bytes()
        assert len(raw) == 2 * C.MODEL_SAMPLES * 4, "bad .bin size for %s" % fr["input_file"]
        assert C.sha256_bytes(raw) == fr["model_input_sha256"], (
            "input SHA mismatch for %s" % fr["input_file"])
        iq = C.load_tensor_2x1024(bin_path)
        ev = build_tx_payload(iq)
        payload_file = "%d.i16" % fr["selection_id"]
        (out / payload_file).write_bytes(ev["payload_i16"].tobytes())
        psha = C.sha256_bytes(ev["payload_i16"].tobytes())
        if ev["clip_pre"] or ev["clip_post"]:
            clip_count += 1
        rows.append([
            fr["selection_id"], fr["hdf5_row_index"], fr["raw24_class"],
            fr["modulation"], fr["dataset_snr_db"], fr["input_file"],
            fr["model_input_sha256"], fr["host_pred"],
            payload_file, psha,
            "%.9f" % ev["native_rms"], "%.9f" % ev["tx_scale"],
            "%.9f" % ev["unscale"],
            "%.3f" % ev["peak_pre"], "%.3f" % ev["peak_post"],
            1 if ev["clip_pre"] else 0, 1 if ev["clip_post"] else 0,
            "cyclic_tile_1024_to_53760_rms2048_ci16",
        ])
        sha_lines.append("%s  %s" % (psha, payload_file))

    # 写 manifest + SHA256SUMS
    with open(out / "tx_manifest.tsv", "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(TX_MANIFEST_HEADER) + "\n")
        for r in rows:
            f.write("\t".join(str(v) for v in r) + "\n")
    with open(out / "SHA256SUMS.txt", "w", encoding="utf-8", newline="") as f:
        for line in sha_lines:
            f.write(line + "\n")

    assert clip_count == 0, "%d frames clip (native RMS -> 2048 不应裁剪)" % clip_count
    print("RADIOML_DUALSDR_TX_PAYLOAD frames=%d clip=%d out_dir=%s" %
          (len(frames), clip_count, out))
    print("RADIOML_DUALSDR_TX_PAYLOAD_DONE")


if __name__ == "__main__":
    main()
