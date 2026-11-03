#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
radioml_public_protocol_tx.py -- fix1 主验收臂 TX 侧：公共协议 24 纯净调制波形打包
（PC host，纯离线，不碰板/不发射/不训练）。

把 24 个纯净调制波形（复用 blind-clean1 同种子 seed_base=3000000，不新增帧）逐字
包装进公共协议 burst（前导 ZC + settling-zero + 16QAM 训练块 + 载荷 + guard-zero +
ZC 尾），并固化**同源绑定**（第 4 节）：

  同源三键 = (source_id, conversion_version, input_sha)
    source_id           = fix1-public-protocol-24waveforms   （显式，非原始 480 帧）
    conversion_version  = v1                                  （转换版本）
    input_sha           = model_input_sha256（A 层原始 [2,1024] f32 的 SHA）

source_index 显式 == class_index+1（不 shuffle，不冒充盲采/480 帧配对）。每行还固化
burst_sha256（传输绑定）与 payload_ci16_sha256（B 层量化绑定）。

输出（--out-dir 必须不存在）：
    public_protocol_tx_manifest.tsv   （10 列，同源绑定）
    <source_index>.burst.i16          119808 int16（59904 复）突发
    SHA256SUMS.txt                    每文件 SHA
    public_protocol_tx_summary.json   冻结常量 + 生成核验
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_independent_rx_contract as IRX  # noqa: E402
import radioml_clean_contract as GEN            # noqa: E402

TOKEN = "M29-RML24-FIX10CLASS24-INDEPENDENT-RX-DELIVERY-FIX1-TX-PACKAGE"

MANIFEST_HEADER = [
    "source_id", "conversion_version", "source_index", "class_index", "class_name",
    "seed", "burst_file", "burst_sha256", "payload_ci16_sha256", "model_input_sha256",
]


def build_rows():
    rows = []
    for ci in range(IRX.N_CLASSES):
        name = GEN.LABEL_ORDER_24[ci]
        seed = IRX.SEED_BASE + ci
        wf = IRX.generate_waveform(ci)
        payload_ci16 = IRX.quantize_ci16(wf, IRX.TX_DIGITAL_SCALE)  # 1024 复
        burst = IRX.build_public_protocol_burst(wf)
        sid = ci + 1
        rows.append({
            "source_id": IRX.SOURCE_ID,
            "conversion_version": IRX.CONVERSION_VERSION,
            "source_index": sid,
            "class_index": ci,
            "class_name": name,
            "seed": seed,
            "burst_file": "%d.burst.i16" % sid,
            "burst_sha256": IRX.sha256_bytes(burst.tobytes()),
            "payload_ci16_sha256": IRX.sha256_bytes(payload_ci16.tobytes()),
            "model_input_sha256": IRX.sha256_bytes(IRX.tensor_to_bytes(wf)),
        })
    return rows


def write_tx_package(out_dir: Path) -> dict:
    if out_dir.exists():
        raise SystemExit("ERROR: --out-dir already exists (refuse overwrite): %s" % out_dir)
    out_dir.mkdir(parents=True)

    rows = build_rows()
    sha_lines = []
    for r in rows:
        ci = r["class_index"]
        burst = IRX.build_public_protocol_burst(IRX.generate_waveform(ci))
        (out_dir / r["burst_file"]).write_bytes(burst.tobytes())
        sha_lines.append("%s  %s" % (r["burst_sha256"], r["burst_file"]))

    with open(out_dir / "public_protocol_tx_manifest.tsv", "w",
              encoding="utf-8", newline="\n") as f:
        f.write("\t".join(MANIFEST_HEADER) + "\n")
        for r in rows:
            f.write("\t".join([
                r["source_id"], r["conversion_version"], str(r["source_index"]),
                str(r["class_index"]), r["class_name"], str(r["seed"]),
                r["burst_file"], r["burst_sha256"], r["payload_ci16_sha256"],
                r["model_input_sha256"],
            ]) + "\n")

    with open(out_dir / "SHA256SUMS.txt", "w", encoding="utf-8", newline="\n") as f:
        for line in sorted(sha_lines):
            f.write(line + "\n")

    summary = {
        "token": TOKEN,
        "frozen_constants": {
            "tx_digital_scale": IRX.TX_DIGITAL_SCALE,
            "model_input_norm": IRX.MODEL_INPUT_NORM,
            "seed_base": IRX.SEED_BASE,
            "source_id": IRX.SOURCE_ID,
            "conversion_version": IRX.CONVERSION_VERSION,
            "public_protocol_layout": {
                "preamble_complex": IRX.K_PREAMBLE_COMPLEX,
                "payload_training_complex": IRX.K_PAYLOAD_TRAINING_COMPLEX,
                "payload_complex": IRX.K_PAYLOAD_COMPLEX,
                "tail_complex": IRX.K_TAIL_COMPLEX,
                "total_burst_complex": IRX.K_TOTAL_BURST_COMPLEX,
                "payload_training_amp": IRX.K_PAYLOAD_TRAINING_AMP,
            },
        },
        "same_source_binding": "source_id + conversion_version + model_input_sha256",
        "n_sources": IRX.N_CLASSES,
        "per_class": {
            r["class_name"]: {
                "class_index": r["class_index"],
                "source_index": r["source_index"],
                "seed": r["seed"],
                "burst_sha256": r["burst_sha256"],
                "payload_ci16_sha256": r["payload_ci16_sha256"],
                "model_input_sha256": r["model_input_sha256"],
            } for r in rows
        },
    }
    with open(out_dir / "public_protocol_tx_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=True)

    print("RADIOML_PUBLIC_PROTOCOL_TX sources=%d out_dir=%s" % (len(rows), out_dir))
    print("RADIOML_PUBLIC_PROTOCOL_TX_DONE")
    return summary


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()
    if args.self_test:
        return self_test()
    if not args.out_dir:
        ap.error("--out-dir=<fresh dir> is required (or --self-test)")
    write_tx_package(Path(args.out_dir))
    return 0


def self_test() -> int:
    checks = []
    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print("SELF-TEST %-56s %s%s" % (name, "PASS" if ok else "FAIL",
                                        (" -- " + detail) if detail else ""))

    rows = build_rows()
    check("24 sources", len(rows) == IRX.N_CLASSES)
    check("source_index == class_index+1 (explicit, not shuffled)",
          all(r["source_index"] == r["class_index"] + 1 for r in rows))
    check("source_id is public-protocol (not 480-frame)",
          all(r["source_id"] == IRX.SOURCE_ID for r in rows))
    check("conversion_version v1",
          all(r["conversion_version"] == IRX.CONVERSION_VERSION for r in rows))
    # 同源绑定：A 层原始 [2,1024] 由 (class, seed) 可复现，SHA 稳定。
    r0 = rows[0]
    wf0 = IRX.generate_waveform(r0["class_index"])
    check("model_input_sha256 reproducible from (class,seed)",
          IRX.sha256_bytes(IRX.tensor_to_bytes(wf0)) == r0["model_input_sha256"])
    # burst 长度与确定性包装块一致。
    b = IRX.build_public_protocol_burst(IRX.generate_waveform(0))
    check("burst size == 119808 int16", b.size == 2 * IRX.K_TOTAL_BURST_COMPLEX)
    # 每类 burst_sha256 稳定（两次构建逐字节一致）。
    b2 = IRX.build_public_protocol_burst(IRX.generate_waveform(0))
    check("burst deterministic", IRX.sha256_bytes(b.tobytes()) ==
          IRX.sha256_bytes(b2.tobytes()))

    all_ok = all(checks)
    print("RADIOML_PUBLIC_PROTOCOL_TX_SELF_TEST %s (%d/%d)" %
          ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
