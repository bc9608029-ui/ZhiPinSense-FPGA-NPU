#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
freeze_v2_baseline.py -- 冻结 v2 数字判读基线（板测前收口第 3 点）。

读取 v2 公共协议 manifest（10 列）+ 数字回放三层 TSV（19 列），逐样本：
  * 对齐核验（source_index 连续 1..24、class_index 与 manifest 一致）；
  * 逐样本 SHA 绑定：manifest A 层 model_input_sha256（波形身份）+ 回放 recovered
    model_input_sha256（数字恢复后实际喂模型的张量），两者都写入冻结文件；
  * 可选核验 layers 目录 recovered tensor 字节 SHA（--layers-dir）；
  * orig 层预测 = 冻结数字基线（v2 orig 23/24，AM-DSB-SC -> 256QAM 如实记录）。

产物（默认 baseline/v2_digital_baseline_frozen.json）：一个确定性 JSON，逐样本行 +
SHA 绑定 + 顶层摘要，并打印文件 SHA256（供回报与台账）。

纯离线；只读判定；不碰板/不发射/不训练。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

TOKEN = "M29-RML24-FIX10CLASS24-V2-DIGITAL-BASELINE-FROZEN"
SOURCE_ID = "fix1v2-waveform-corrected-24waveforms"
CONVERSION_VERSION = "v2"
N_SOURCES = 24


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_manifest(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].rstrip("\n").split("\t")
    assert header[0] == "source_id" and header[2] == "source_index", "manifest header"
    rows = {}
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.rstrip("\n").split("\t")
        sid = int(f[2])
        rows[sid] = {
            "source_id": f[0], "conversion_version": f[1], "source_index": sid,
            "class_index": int(f[3]), "class_name": f[4], "seed": int(f[5]),
            "burst_file": f[6], "burst_sha256": f[7],
            "payload_ci16_sha256": f[8], "model_input_sha256": f[9],
        }
    return rows


def load_replay(path: Path):
    lines = path.read_text(encoding="utf-8").splitlines()
    header = lines[0].rstrip("\n").split("\t")
    assert header[0] == "source_index" and header[3] == "orig_pred", "replay header"
    rows = {}
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.rstrip("\n").split("\t")
        sid = int(f[0])
        rows[sid] = {
            "source_index": sid, "class_index": int(f[1]), "class_name": f[2],
            "orig_pred": int(f[3]), "recovered_pred": int(f[5]),
            "rotated_pred": int(f[7]), "finite": int(f[9]),
            "corr": float(f[16]), "residual": float(f[17]),
            "recovered_model_input_sha256": f[18],
        }
    return rows


def freeze(manifest_path, replay_path, layers_dir, out_json):
    mr = load_manifest(manifest_path)
    rr = load_replay(replay_path)

    errors, warnings = [], []
    # 对齐：source_index 连续 1..24，class_index 一致
    for sid in range(1, N_SOURCES + 1):
        if sid not in mr:
            errors.append("manifest missing source_index=%d" % sid)
        if sid not in rr:
            errors.append("replay missing source_index=%d" % sid)
    for sid, r in rr.items():
        m = mr.get(sid)
        if m is None:
            errors.append("replay source_index=%d not in manifest" % sid)
            continue
        if r["class_index"] != m["class_index"]:
            errors.append("class_index mismatch source_index=%d" % sid)
        if m["source_id"] != SOURCE_ID or m["conversion_version"] != CONVERSION_VERSION:
            errors.append("manifest identity mismatch source_index=%d (%s/%s)"
                          % (sid, m["source_id"], m["conversion_version"]))

    # 逐样本 SHA 绑定：recovered tensor 字节 SHA 核验（可选 layers-dir）
    sha_ok, sha_bad = 0, []
    for sid in range(1, N_SOURCES + 1):
        sha = rr.get(sid, {}).get("recovered_model_input_sha256")
        if layers_dir is None:
            sha_bad.append("source_index=%d no --layers-dir" % sid)
            continue
        f = layers_dir / ("%d.recovered.tensor.bin" % sid)
        if not f.is_file():
            sha_bad.append("source_index=%d recovered tensor missing" % sid)
            continue
        recomputed = sha256_hex(f.read_bytes())
        if recomputed != sha:
            sha_bad.append("source_index=%d recovered SHA mismatch" % sid)
        else:
            sha_ok += 1

    samples = []
    for sid in range(1, N_SOURCES + 1):
        m = mr[sid]
        r = rr.get(sid, {})
        orig_pred = r.get("orig_pred", -1)
        orig_correct = 1 if orig_pred == m["class_index"] else 0
        samples.append({
            "source_index": sid,
            "class_index": m["class_index"],
            "class_name": m["class_name"],
            "seed": m["seed"],
            "burst_file": m["burst_file"],
            "burst_sha256": m["burst_sha256"],
            "payload_ci16_sha256": m["payload_ci16_sha256"],
            "manifest_model_input_sha256": m["model_input_sha256"],
            "recovered_model_input_sha256": r.get("recovered_model_input_sha256", ""),
            "orig_pred": orig_pred,
            "orig_correct": orig_correct,
        })

    n_orig_correct = sum(s["orig_correct"] for s in samples)
    orig_mis = [{"source_index": s["source_index"], "class": s["class_name"],
                 "orig_pred": s["orig_pred"]} for s in samples if s["orig_correct"] == 0]

    baseline = {
        "token": TOKEN,
        "built_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "baseline_kind": "v2_digital_orig",
        "source_id": SOURCE_ID,
        "conversion_version": CONVERSION_VERSION,
        "n_sources": N_SOURCES,
        "orig_correct": "%d/%d" % (n_orig_correct, N_SOURCES),
        "orig_misclassified": orig_mis,
        "model_vs_new_waveform_domain_mismatch": len(orig_mis) > 0,
        "sha_binding": {
            "manifest_model_input_sha256": "A 层原始干净波形模型输入 SHA（波形身份绑定）",
            "recovered_model_input_sha256": "数字恢复后实际喂模型张量 SHA（预测绑定）",
        },
        "errors": errors,
        "warnings": warnings,
        "recovered_tensor_sha_verified": "%d/%d" % (sha_ok, sha_ok + len(sha_bad))
        if layers_dir is not None else "n/a (--layers-dir not given)",
        "sha_bad": sha_bad,
        "honest_note": ("v2 修正波形数字直送 orig 23/24：AM-DSB-SC(源21) 被冻结 BF16 "
                        "判为 256QAM。如实记录为『模型与新波形域不匹配』，不掩盖、"
                        "不归因 RF、不反向改波形。"),
        "samples": samples,
    }

    out_json = Path(out_json)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(baseline, indent=2, sort_keys=True, ensure_ascii=False)
    data = text.encode("utf-8")
    # 写原始字节（不经 Windows 换行翻译），保证文件 SHA == 下面打印的 file_sha256，
    # 否则 write_text 会把 \n 转 \r\n 导致打印 SHA 与磁盘文件 SHA 不一致。
    out_json.write_bytes(data)
    file_sha = sha256_hex(data)
    print("FREEZE_V2_BASELINE n=%d orig_correct=%d/%d errors=%d sha_bad=%d" %
          (N_SOURCES, n_orig_correct, N_SOURCES, len(errors), len(sha_bad)))
    print("FREEZE_V2_BASELINE out=%s" % out_json)
    print("FREEZE_V2_BASELINE file_sha256=%s" % file_sha)
    print("FREEZE_V2_BASELINE_DONE")
    return baseline


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default="")
    ap.add_argument("--replay", default="")
    ap.add_argument("--layers-dir", default=None)
    ap.add_argument("--out-json", default="")
    args = ap.parse_args()
    if not args.manifest or not args.replay or not args.out_json:
        ap.error("--manifest --replay --out-json required")
    freeze(Path(args.manifest), Path(args.replay),
           Path(args.layers_dir) if args.layers_dir else None,
           Path(args.out_json))
    return 0


if __name__ == "__main__":
    sys.exit(main())
