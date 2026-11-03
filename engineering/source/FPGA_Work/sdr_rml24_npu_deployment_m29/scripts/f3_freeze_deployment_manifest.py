#!/usr/bin/env python
"""M29 Phase F3 — freeze the 23-class deployment manifest (write-once).

Writes ``deploy/rml23_merged_deployment_manifest.json`` for the F2-selected
candidate (expA_bf16_head).  The file is write-once: if it already exists this
script refuses to overwrite (fail-closed), and a ``--force-identical`` must not
silently overwrite either — the only accepted path is a fresh write.

Read-only w.r.t. all source artifacts; it re-verifies the selected candidate's
identity (json/raw SHA + params_md5 + target) before writing.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

ROOT = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29"
TMP = r"F:\FPGA_Work"

sys.path.insert(0, os.path.join(ROOT, "contracts"))
from rml23_merged_contract import (  # noqa: E402
    DEPLOYED_LABEL_ORDER_23, SOURCE_LABEL_ORDER_24, SOURCE_LABEL_CONTRACT_SHA256,
    label_order_23_sha256, merged_contract_sha256, canonical_contract,
)

# --- selected candidate identity (F2 verdict) ------------------------------
SELECTED = {
    "json": os.path.join(TMP, "_tmp_24class_expA_bf16_head_384_20261010",
                         "jsonraw", "model_24class_ZG.json"),
    "raw": os.path.join(TMP, "_tmp_24class_expA_bf16_head_384_20261010",
                        "jsonraw", "model_24class_ZG.raw"),
    "json_sha": "d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d",
    "raw_sha": "2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba",
    "params_md5": "7966a4829fc713b2e8ea6c04168be263",
    "target_device": "@zhuget(330)",
}
SOURCE_CHECKPOINT = r"F:\FPGA_Work\24class_results\rml24_seed2027_best.pt"
SOURCE_CHECKPOINT_SHA = "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d"
SUBSET = os.path.join(ROOT, "work", "eval_full", "subset_index.npz")
SELECTION_EVIDENCE = os.path.join(ROOT, "artifacts",
                                  "m29_rml23_merged_candidate_comparison.json")

# Frozen preprocessing contract (the board input contract, unchanged since D.3)
PREPROCESSING_CONTRACT = {
    "input_shape": [1, 2, 1024],
    "input_dtype": "float32",
    "input_layout": "planar_iq_real_then_imag",
    "sample_derivation": "hdf5_X[row]_1024x2_transpose_to_2x1024_c_order",
    "byte_order": "little_endian",
    "sample_bytes": 8192,
    "normalization": "none_rms_already_1.0",
    "no_transinput": True,
}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_json(obj) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def main() -> int:
    print("== M29 Phase F3: freeze deployment manifest ==")

    # identity verification (fail-closed)
    assert sha256_file(SELECTED["json"]) == SELECTED["json_sha"], "json SHA"
    assert sha256_file(SELECTED["raw"]) == SELECTED["raw_sha"], "raw SHA"
    assert sha256_file(SOURCE_CHECKPOINT) == SOURCE_CHECKPOINT_SHA, "checkpoint SHA"
    with open(SELECTED["json"], "r", encoding="utf-8") as f:
        jm = json.load(f)
    assert jm.get("params_md5") == SELECTED["params_md5"], "params_md5"
    assert jm.get("ai_target") == SELECTED["target_device"], "ai_target"
    print("  [OK] selected candidate identity (json/raw/params_md5/target)")
    print("  [OK] source checkpoint identity")

    manifest = {
        "deployment_name": "RML23-AMSSB-MERGED",
        "deployment_mode": "AMSSB_MERGED",
        "source_model_name": "RML2018_24_BENCHMARK",
        "source_checkpoint_sha256": SOURCE_CHECKPOINT_SHA,
        "source_npu_json_sha256": SELECTED["json_sha"],
        "source_npu_raw_sha256": SELECTED["raw_sha"],
        "params_md5": SELECTED["params_md5"],
        "target_device": SELECTED["target_device"],
        "source_output_dim": 24,
        "npu_output_dim": 24,
        "deployed_class_count": 23,
        "source_label_contract_sha256": SOURCE_LABEL_CONTRACT_SHA256,
        "merged_label_contract_sha256": label_order_23_sha256(),
        "merged_contract_sha256": merged_contract_sha256(),
        "amssb_source_indices": [17, 18],
        "amssb_source_names": ["AM-SSB-WC", "AM-SSB-SC"],
        "amssb_deployed_index": 17,
        "amssb_deployed_name": "AM-SSB",
        "merge_algorithm": "logaddexp(logit_AM_SSB_SC, logit_AM_SSB_WC)",
        "preprocessing_contract": PREPROCESSING_CONTRACT,
        "preprocessing_contract_sha256": sha256_json(PREPROCESSING_CONTRACT),
        "source_label_order_24": list(SOURCE_LABEL_ORDER_24),
        "deployed_label_order_23": list(DEPLOYED_LABEL_ORDER_23),
        "validation": {
            "split": "radioml2018_validation",
            "subset_seed": 2028,
            "subset_per_class": 64,
            "subset_size": 1536,
            "subset_index_npz_sha256": sha256_file(SUBSET),
            "note": "subset_index.npz sub_fp32/sub_int8 are argmax preds; FP32 raw logits recomputed via ONNX",
        },
        "candidate_selection_evidence_sha256": sha256_file(SELECTION_EVIDENCE),
        "expert_enabled": False,
        "expert_result": "NOT_RUN",
        "final_test_accessed": False,
        "ood_final_test_accessed": False,
    }

    out_path = os.path.join(ROOT, "deploy", "rml23_merged_deployment_manifest.json")
    if os.path.exists(out_path):
        print(f"  FAIL: manifest already exists ({out_path}); write-once refused")
        return 1
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"  wrote {out_path}")
    print("  merged_label_contract_sha256 =", manifest["merged_label_contract_sha256"])
    print("  merged_contract_sha256       =", manifest["merged_contract_sha256"])
    print("  preprocessing_contract_sha256 =", manifest["preprocessing_contract_sha256"])
    print("  candidate_selection_evidence_sha256 =",
          manifest["candidate_selection_evidence_sha256"])
    print("== F3 done ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
