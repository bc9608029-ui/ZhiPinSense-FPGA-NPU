#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
radioml_v2_tx.py -- 波形正确性 v2 TX 侧：24 个 v2 波形 -> 公共协议 burst 打包。
纯离线、不碰板/不发射/不训练。结构与 fix1 的 public_protocol_tx 相同，只换 v2 波形源
与 v2 幅度常数（S_v2），同源绑定独立为 v2。

输出（--out-dir 必须不存在）：
    public_protocol_tx_manifest.tsv   10 列，source_id=fix1v2-... conversion_version=v2
    <source_index>.burst.i16          119808 int16
    SHA256SUMS.txt / summary json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_v2_contract as V2          # noqa: E402
import radioml_independent_rx_contract as V1  # noqa: E402
import radioml_clean_contract as GEN      # noqa: E402

TOKEN = "M29-RML24-FIX10CLASS24-WAVEFORM-CORRECT-V2-TX"

MANIFEST_HEADER = [
    "source_id", "conversion_version", "source_index", "class_index", "class_name",
    "seed", "burst_file", "burst_sha256", "payload_ci16_sha256", "model_input_sha256",
]


def build_rows():
    rows = []
    for ci in range(V2.N_CLASSES):
        name = GEN.LABEL_ORDER_24[ci]
        seed = V2.SEED_BASE + ci
        wf = V2.generate_waveform_v2(ci)
        payload_ci16 = V1.quantize_ci16(wf, V2.TX_DIGITAL_SCALE_V2)
        burst = V2.build_public_protocol_burst_v2(wf)
        sid = ci + 1
        rows.append({
            "source_id": V2.SOURCE_ID_V2,
            "conversion_version": V2.CONVERSION_VERSION_V2,
            "source_index": sid,
            "class_index": ci,
            "class_name": name,
            "seed": seed,
            "burst_file": "%d.burst.i16" % sid,
            "burst_sha256": V1.sha256_bytes(burst.tobytes()),
            "payload_ci16_sha256": V1.sha256_bytes(payload_ci16.tobytes()),
            "model_input_sha256": V1.sha256_bytes(V1.tensor_to_bytes(wf)),
        })
    return rows


def write_tx_package(out_dir: Path) -> dict:
    if out_dir.exists():
        raise SystemExit("ERROR: --out-dir already exists (refuse overwrite): %s" % out_dir)
    out_dir.mkdir(parents=True)
    rows = build_rows()
    sha_lines = []
    for r in rows:
        burst = V2.build_public_protocol_burst_v2(V2.generate_waveform_v2(r["class_index"]))
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
        "amplitude_contract_v2": {
            "max_peak_v2": V2.MAX_PEAK_V2,
            "max_peak_class_v2": V2.MAX_PEAK_CLASS_V2,
            "tx_digital_scale_S_v2": V2.TX_DIGITAL_SCALE_V2,
            "model_input_norm_v2": V2.MODEL_INPUT_NORM_V2,
        },
        "same_source_binding": "source_id + conversion_version + model_input_sha256",
        "source_id": V2.SOURCE_ID_V2,
        "conversion_version": V2.CONVERSION_VERSION_V2,
        "n_sources": V2.N_CLASSES,
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
    print("RADIOML_V2_TX sources=%d out_dir=%s S_v2=%.9f" %
          (len(rows), out_dir, V2.TX_DIGITAL_SCALE_V2))
    print("RADIOML_V2_TX_DONE")
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
    check("24 sources", len(rows) == V2.N_CLASSES)
    check("source_index == class_index+1",
          all(r["source_index"] == r["class_index"] + 1 for r in rows))
    check("source_id is v2 (not v1/480-frame)",
          all(r["source_id"] == V2.SOURCE_ID_V2 for r in rows))
    check("conversion_version v2",
          all(r["conversion_version"] == V2.CONVERSION_VERSION_V2 for r in rows))
    r0 = rows[0]
    wf0 = V2.generate_waveform_v2(r0["class_index"])
    check("model_input_sha256 reproducible",
          V1.sha256_bytes(V1.tensor_to_bytes(wf0)) == r0["model_input_sha256"])
    b = V2.build_public_protocol_burst_v2(V2.generate_waveform_v2(0))
    check("burst size == 119808 int16", b.size == 2 * V1.K_TOTAL_BURST_COMPLEX)
    b2 = V2.build_public_protocol_burst_v2(V2.generate_waveform_v2(0))
    check("burst deterministic", V1.sha256_bytes(b.tobytes()) ==
          V1.sha256_bytes(b2.tobytes()))
    all_ok = all(checks)
    print("RADIOML_V2_TX_SELF_TEST %s (%d/%d)" %
          ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
