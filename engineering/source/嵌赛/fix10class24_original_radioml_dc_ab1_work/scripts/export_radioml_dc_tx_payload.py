#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_radioml_dc_tx_payload.py -- dc-transport TX 派生 CI16 payload 导出
(fix10class24-original-radioml-dc-ab1)。

把 npu-ab1 的 480 帧输入包读入, 对每帧执行**移除 DC -> 铺排 AC -> CI16(RMS2048)**的
确定性、类无关适配, 生成生产 RF 链可发射的 CI16 payload (53760 复样本, 只含 AC 分量),
并逐帧记录 DC 参数 / SHA / 幅度 / 缩放 / 裁剪证据, 供板端 RX 恢复后「还原尺度 + 加回 DC」。

关键: 复用 direct 契约的**同一套** lround / CI16 / RMS2048 / 循环铺排机器
(scripts/radioml_dualsdr_common.py), 只是把被量化的对象从「原始 IQ」换成「去 DC 的 AC」,
并额外记录 dc_i/dc_q/ac_rms/inverse_scale 四列。direct 的 export 脚本保持逐字节不变
(export_radioml_dualsdr_tx_payload.py, 本任务 vendored verbatim)。

RMS 口径: ac_rms = 复 RMS (sqrt(mean(|ac|^2))), 与生产 native_rms 一致; TX AC 目标
RMS2048 = 复 RMS 2048 (非 per-I/Q 分量 RMS)。

用法:
    python -I scripts/export_radioml_dc_tx_payload.py \
        --input-package <npu-ab1 input_package dir> \
        --out-dir <fresh dc tx payload dir>
输出 (out-dir 必须不存在):
    <selection_id>.i16           107520 int16 = 53760 复 AC CI16 payload (交错 I0,Q0)
    tx_manifest.tsv              每帧 22 列 (18 主键/证据 + dc_i + dc_q + ac_rms + inverse_scale)
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
import radioml_dc_adapt as DC  # noqa: E402
from export_radioml_dualsdr_tx_payload import parse_npu_ab_manifest  # noqa: E402

# direct 18 列表头 (供追加 DC 4 列)。
DIRECT_HEADER = [
    "selection_id", "hdf5_row_index", "raw24_class", "modulation",
    "dataset_snr_db", "input_file", "model_input_sha256", "host_pred",
    "tx_payload_file", "tx_payload_sha256", "native_rms", "tx_scale",
    "unscale", "peak_pre", "peak_post", "clip_pre", "clip_post",
    "adaptation",
]
# dc-transport 22 列表头 (18 列语义见 radioml_dc_adapt.py, 追加 4 列 DC 证据)。
DC_EXTRA_HEADER = ["dc_i", "dc_q", "ac_rms", "inverse_scale"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input-package", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    src = Path(args.input_package)
    out = Path(args.out_dir)
    if out.exists():
        print("ERROR: --out-dir already exists (refuse overwrite): %s" % out,
              file=sys.stderr)
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

        fwd = DC.adapt_forward(iq)
        payload_file = "%d.i16" % fr["selection_id"]
        (out / payload_file).write_bytes(fwd["payload_i16"].tobytes())
        psha = C.sha256_bytes(fwd["payload_i16"].tobytes())
        if fwd["clip_pre"] or fwd["clip_post"]:
            clip_count += 1

        # native_rms = 原始 IQ RMS (provenance); tx_scale = 2048/ac_rms (TX 量化);
        # unscale = inverse_scale = ac_rms/2048 (counts -> AC f32 域)。
        rows.append([
            fr["selection_id"], fr["hdf5_row_index"], fr["raw24_class"],
            fr["modulation"], fr["dataset_snr_db"], fr["input_file"],
            fr["model_input_sha256"], fr["host_pred"],
            payload_file, psha,
            "%.9f" % C.native_rms(iq), "%.9f" % fwd["tx_scale"],
            "%.9f" % fwd["inverse_scale"],
            "%.3f" % fwd["peak_pre"], "%.3f" % fwd["peak_post"],
            1 if fwd["clip_pre"] else 0, 1 if fwd["clip_post"] else 0,
            DC.ADAPTATION_DC_TRANSPORT,
            "%.9f" % fwd["dc_i"], "%.9f" % fwd["dc_q"],
            "%.9f" % fwd["ac_rms"], "%.9f" % fwd["inverse_scale"],
        ])
        sha_lines.append("%s  %s" % (psha, payload_file))

    with open(out / "tx_manifest.tsv", "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(DIRECT_HEADER + DC_EXTRA_HEADER) + "\n")
        for r in rows:
            f.write("\t".join(str(v) for v in r) + "\n")
    with open(out / "SHA256SUMS.txt", "w", encoding="utf-8", newline="") as f:
        for line in sha_lines:
            f.write(line + "\n")

    # direct 契约 assert clip_count == 0; dc-transport 同样记录并断言 (去 DC 后峰值应
    # 不增, 若有裁剪则说明某帧 AC 超 32767 峰, 需离线复查, 不静默放行)。
    assert clip_count == 0, "%d frames clip (AC RMS -> 2048 不应裁剪)" % clip_count
    print("RADIOML_DC_TX_PAYLOAD frames=%d clip=%d out_dir=%s" %
          (len(frames), clip_count, out))
    print("RADIOML_DC_TX_PAYLOAD_DONE")


if __name__ == "__main__":
    main()
