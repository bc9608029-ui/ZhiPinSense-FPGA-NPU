#!/usr/bin/env python
"""M29 Phase F0 — read-only artifact inventory.

Collects, without writing any status marker and without touching test/board:
  * shape/dtype of every saved icraft-run logits/preds .npy
  * shape/dtype/keys of the 1536 diagnostic subset_index.npz
  * SHA256 of every candidate's model_24class_ZG.json/.raw (384 / expA / DRA384)
  * params_md5 + ai_target (+ output shape) extracted from each ZG.json
  * SHA256 of the FP32 source (checkpoint, ONNX, frozen label contract)

Everything is read-only. Writes the register JSON to artifacts/ (a NEW file, not a
status marker) and prints a summary.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import numpy as np  # noqa: E402

ROOT = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29"
TMP = r"F:\FPGA_Work"

CHECKPOINT = r"F:\FPGA_Work\24class_results\rml24_seed2027_best.pt"
ONNX = os.path.join(ROOT, "work", "onnx", "rml24_24class_opset17.onnx")
FROZEN_CONTRACT = os.path.join(ROOT, "_frozen", "contracts", "rml24_contract.py")
SUBSET = os.path.join(ROOT, "work", "eval_full", "subset_index.npz")

CANDIDATES = {
    "d384_int8": {
        "desc": "Phase D 384-baseline full-INT8 (op179 int8)",
        "json": os.path.join(TMP, "_tmp_24class_adapt_generate_384_20261010",
                             "jsonraw", "model_24class_ZG.json"),
        "raw": os.path.join(TMP, "_tmp_24class_adapt_generate_384_20261010",
                            "jsonraw", "model_24class_ZG.raw"),
        "logits": os.path.join(ROOT, "work", "eval_quant", "quant_logits.npy"),
        "preds": os.path.join(ROOT, "work", "eval_quant", "quant_preds.npy"),
    },
    "expA_bf16_head": {
        "desc": "Phase D.1 experiment A: front INT8 + classification head (op179) BF16",
        "json": os.path.join(TMP, "_tmp_24class_expA_bf16_head_384_20261010",
                             "jsonraw", "model_24class_ZG.json"),
        "raw": os.path.join(TMP, "_tmp_24class_expA_bf16_head_384_20261010",
                            "jsonraw", "model_24class_ZG.raw"),
        "logits": os.path.join(TMP, "_tmp_24class_expA_bf16_head_384_20261010_eval_result",
                               "expA_logits.npy"),
        "preds": os.path.join(TMP, "_tmp_24class_expA_bf16_head_384_20261010_eval_result",
                              "expA_preds.npy"),
    },
    "dra384_int8": {
        "desc": "Phase D.3 dynamic-range-aware recalibration, 384 full-INT8",
        "json": os.path.join(TMP, "_tmp_24class_dra_384_20261011",
                             "jsonraw", "model_24class_ZG.json"),
        "raw": os.path.join(TMP, "_tmp_24class_dra_384_20261011",
                            "jsonraw", "model_24class_ZG.raw"),
        "logits": os.path.join(TMP, "_tmp_24class_dra_384_20261011_eval_result",
                               "dra384_logits.npy"),
        "preds": os.path.join(TMP, "_tmp_24class_dra_384_20261011_eval_result",
                              "dra384_preds.npy"),
    },
}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def npy_info(path: str) -> dict | None:
    if not os.path.exists(path):
        return None
    a = np.load(path, allow_pickle=False)
    return {"path": path, "shape": list(a.shape), "dtype": str(a.dtype),
            "size": int(a.size), "bytes": int(os.path.getsize(path))}


def json_meta(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    out = {}
    for key in ("params_md5", "ai_target", "target", "net_name", "name"):
        if key in data:
            out[key] = data[key]
    # output shape: look for the output node / net output tensor
    for key in ("output", "outputs", "out_shape", "output_shape"):
        if key in data:
            out[key] = data[key]
    # try to locate output tensor shape from common fields
    if "outputs" not in out:
        for node in data.get("nodes", []) or data.get("operators", []) or []:
            if node.get("type") == "Output" or node.get("_type_key") == "Output":
                out["_output_node"] = node
                break
    return out


def main() -> int:
    reg = {"phase": "M29-Phase-F0-artifact-inventory", "read_only": True,
           "test_split_touched": False, "candidates": {}}

    print("== M29 Phase F0 artifact inventory (read-only) ==\n")

    # 1) subset_index.npz
    with np.load(SUBSET, allow_pickle=False) as z:
        sub = {k: {"shape": list(z[k].shape), "dtype": str(z[k].dtype)} for k in z.files}
    print(f"[subset] {SUBSET}")
    for k, v in sub.items():
        print(f"    {k}: shape={v['shape']} dtype={v['dtype']}")
    reg["subset"] = {"path": SUBSET, "sha256": sha256_file(SUBSET),
                     "arrays": sub, "note": "sub_fp32/sub_int8 are int64 ARGMAX preds, "
                     "NOT raw logits; FP32 raw 24-dim logits are NOT saved on disk"}

    # 2) FP32 sources
    reg["fp32_source"] = {
        "checkpoint": {"path": CHECKPOINT, "sha256": sha256_file(CHECKPOINT)},
        "onnx": {"path": ONNX, "sha256": sha256_file(ONNX)},
        "frozen_label_contract": {"path": FROZEN_CONTRACT,
                                  "sha256": sha256_file(FROZEN_CONTRACT)},
    }
    print("\n[fp32 source]")
    for k, v in reg["fp32_source"].items():
        print(f"    {k}: {v['sha256']}")

    # 3) candidates
    for name, c in CANDIDATES.items():
        entry = {"desc": c["desc"]}
        entry["json_path"] = c["json"]
        entry["raw_path"] = c["raw"]
        entry["json_sha256"] = sha256_file(c["json"])
        entry["raw_sha256"] = sha256_file(c["raw"])
        entry["json_meta"] = json_meta(c["json"])
        entry["logits"] = npy_info(c["logits"])
        entry["preds"] = npy_info(c["preds"])
        reg["candidates"][name] = entry
        print(f"\n[candidate {name}] {c['desc']}")
        print(f"    json: {entry['json_sha256']}")
        print(f"    raw : {entry['raw_sha256']}")
        print(f"    meta: {json.dumps(entry['json_meta'], ensure_ascii=False)}")
        print(f"    logits: {entry['logits']}")
        print(f"    preds : {entry['preds']}")

    # 4) write register
    out_path = os.path.join(ROOT, "artifacts", "m29_phase_f0_artifact_register.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(reg, f, indent=2, ensure_ascii=False)
    print(f"\nwrote {out_path}")
    print("== F0 inventory done ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
