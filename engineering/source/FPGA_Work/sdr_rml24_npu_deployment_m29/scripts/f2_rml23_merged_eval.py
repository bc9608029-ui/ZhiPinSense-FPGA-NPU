#!/usr/bin/env python
"""M29 Phase F2 — read-only 23-class merged re-evaluation on the fixed 1536 subset.

For all four candidates (FP32 reference + the three vendor INT8 candidates) it
recomputes the deployed 23-class metrics after the AM-SSB logaddexp merge, on the
SAME samples / order / label mapping.  It then applies the 23-class promotion
gates (all vs FP32) and reports which candidate (if any) passes all of them.

Read-only: it reads the saved INT8 logits (never re-runs icraft-run) and
recomputes the FP32 reference raw logits via ONNX Runtime (bit-exact vs PyTorch,
Top-1 agreement == 1.0).  It writes only the two requested artifacts:

  artifacts/m29_rml23_merged_candidate_comparison.json
  artifacts/m29_rml23_merged_confusion_matrix.csv

No test split, no board, no status markers.
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
SUBSET = os.path.join(ROOT, "work", "eval_full", "subset_index.npz")
ONNX = os.path.join(ROOT, "work", "onnx", "rml24_24class_opset17.onnx")
CHECKPOINT = r"F:\FPGA_Work\24class_results\rml24_seed2027_best.pt"
HDF5_PATH = r"F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5"

sys.path.insert(0, os.path.join(ROOT, "contracts"))
sys.path.insert(0, os.path.join(ROOT, "postprocess"))
from rml23_merged_contract import (  # noqa: E402
    DEPLOYED_CLASS_COUNT, DEPLOYED_LABEL_ORDER_23, SOURCE_TO_DEPLOYED,
    SOURCE_LABEL_ORDER_24, SOURCE_LABEL_CONTRACT_SHA256,
    assert_source_order_matches,
)
from rml23_merged import merge_many_24_to_23  # noqa: E402

EXPECTED_CHECKPOINT_SHA = "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d"
EXPECTED_ONNX_SHA = "976618a131e75f23bd46e04e71a114cbbea245d6afdd4c7ea7fa008e0ce9ed51"

# Registered identity from F0 (identity-verifiable gate)
CANDIDATE_MODELS = {
    "d384_int8": {
        "json": os.path.join(TMP, "_tmp_24class_adapt_generate_384_20261010",
                             "jsonraw", "model_24class_ZG.json"),
        "raw": os.path.join(TMP, "_tmp_24class_adapt_generate_384_20261010",
                            "jsonraw", "model_24class_ZG.raw"),
        "json_sha": "e09f1549ff973763dfad67198536596d9c9ae7b8b6a814369a02ef53b43be06e",
        "raw_sha": "5e7be89471147a642d40ef2f880e607014d913f48b279a79c93e324567dd82f5",
        "logits": os.path.join(ROOT, "work", "eval_quant", "quant_logits.npy"),
    },
    "expA_bf16_head": {
        "json": os.path.join(TMP, "_tmp_24class_expA_bf16_head_384_20261010",
                             "jsonraw", "model_24class_ZG.json"),
        "raw": os.path.join(TMP, "_tmp_24class_expA_bf16_head_384_20261010",
                            "jsonraw", "model_24class_ZG.raw"),
        "json_sha": "d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d",
        "raw_sha": "2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba",
        "logits": os.path.join(TMP, "_tmp_24class_expA_bf16_head_384_20261010_eval_result",
                               "expA_logits.npy"),
    },
    "dra384_int8": {
        "json": os.path.join(TMP, "_tmp_24class_dra_384_20261011",
                             "jsonraw", "model_24class_ZG.json"),
        "raw": os.path.join(TMP, "_tmp_24class_dra_384_20261011",
                            "jsonraw", "model_24class_ZG.raw"),
        "json_sha": "654c2f3d97c76c5724cdd3b5c0da352e07aa830dde4ae3993125a6500cff68c4",
        "raw_sha": "a588814e718ecc97745692647ebed945ae556e60d3d0219c5841d15b5be526b2",
        "logits": os.path.join(TMP, "_tmp_24class_dra_384_20261011_eval_result",
                               "dra384_logits.npy"),
    },
}

AMSSB = 17
OOK = 0


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def pred_23_from_logits(logits24: np.ndarray) -> np.ndarray:
    merged = merge_many_24_to_23(logits24)
    return merged.argmax(axis=1).astype(np.int64)


def label_23(labels24: np.ndarray) -> np.ndarray:
    return np.asarray([SOURCE_TO_DEPLOYED[int(l)] for l in labels24], dtype=np.int64)


def eval_23(labels24, logits24, snrs) -> dict:
    labels24 = np.asarray(labels24, dtype=np.int64)
    logits24 = np.asarray(logits24, dtype=np.float32)
    snrs = np.asarray(snrs, dtype=np.float32)
    n = len(labels24)
    nan_inf = int((~np.isfinite(logits24)).sum())
    y = label_23(labels24)
    p = pred_23_from_logits(logits24)

    cm = np.zeros((DEPLOYED_CLASS_COUNT, DEPLOYED_CLASS_COUNT), dtype=np.int64)
    np.add.at(cm, (y, p), 1)
    row_sum = cm.sum(axis=1)
    per_class = np.divide(np.diag(cm), row_sum,
                          out=np.zeros(DEPLOYED_CLASS_COUNT, dtype=float),
                          where=row_sum > 0)
    correct = (p == y)
    accuracy = float(correct.mean())
    f1s = []
    for c in range(DEPLOYED_CLASS_COUNT):
        tp = cm[c, c]
        fp = cm[:, c].sum() - tp
        fn = row_sum[c] - tp
        f1s.append(2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) > 0 else 0.0)

    def slice_acc(pred):
        sel = correct[pred(snrs)]
        return float(sel.mean()) if len(sel) else 0.0

    min_idx = int(per_class.argmin())

    # AM-SSB diagnostics (24-class raw argmax view, for merge-effect accounting)
    pred24 = logits24.argmax(axis=1).astype(np.int64)
    sc_true = labels24 == 18
    wc_true = labels24 == 17
    amssb_true = (labels24 == 17) | (labels24 == 18)
    sc_to_wc = int((pred24[sc_true] == 17).sum())      # SC misrouted to WC (now absorbed)
    wc_to_sc = int((pred24[wc_true] == 18).sum())      # WC misrouted to SC (now absorbed)
    amssb_to_ook = int((p[amssb_true] == OOK).sum())
    amssb_total = int(amssb_true.sum())

    return {
        "accuracy": accuracy,
        "macro_f1": float(np.mean(f1s)),
        "per_class_accuracy": [float(v) for v in per_class],
        "per_class_names": list(DEPLOYED_LABEL_ORDER_23),
        "min_per_class_accuracy": float(per_class.min()),
        "min_class_idx": min_idx,
        "min_class_name": DEPLOYED_LABEL_ORDER_23[min_idx],
        "rated_0_20_accuracy": slice_acc(lambda s: (s >= 0.0) & (s <= 20.0)),
        "snr_0_accuracy": slice_acc(lambda s: s == 0.0),
        "amssb_merged_accuracy": float(per_class[AMSSB]),
        "nan_inf_count": nan_inf,
        "confusion_23": cm.tolist(),
        "amssb_diagnostics": {
            "amssb_true_total": amssb_total,
            "amssb_sc_to_wc_misroute_24": sc_to_wc,
            "amssb_wc_to_sc_misroute_24": wc_to_sc,
            "amssb_merged_to_ook": amssb_to_ook,
            "amssb_merged_still_ook_ratio": float(amssb_to_ook / amssb_total)
            if amssb_total else 0.0,
        },
    }


def recompute_fp32_logits(sub_indices) -> np.ndarray:
    import onnxruntime as ort
    import h5py
    so = ort.SessionOptions(); so.log_severity_level = 3
    sess = ort.InferenceSession(ONNX, sess_options=so, providers=["CPUExecutionProvider"])
    out = np.empty((len(sub_indices), 24), dtype=np.float32)
    with h5py.File(HDF5_PATH, "r") as f:
        X = f["X"]
        for i, src in enumerate(sub_indices.tolist()):
            raw = np.asarray(X[src], dtype=np.float32)
            planar = np.ascontiguousarray(raw.T)[None, :, :]  # [1,2,1024]
            logits = sess.run(["logits"], {"iq": planar})[0]
            out[i] = logits[0]
    return out


def gate_table(fp32: dict, cand: dict, name: str) -> dict:
    drops = {
        "G1_accuracy": fp32["accuracy"] - cand["accuracy"],
        "G2_macro_f1": fp32["macro_f1"] - cand["macro_f1"],
        "G3_rated_0_20": fp32["rated_0_20_accuracy"] - cand["rated_0_20_accuracy"],
        "G4_snr0": fp32["snr_0_accuracy"] - cand["snr_0_accuracy"],
        "G5_min_class": fp32["min_per_class_accuracy"] - cand["min_per_class_accuracy"],
        "G6_amssb_collapse": fp32["amssb_merged_accuracy"] - cand["amssb_merged_accuracy"],
    }
    # G7: worst per-class drop among the 22 non-AM-SSB classes
    deltas = [fp32["per_class_accuracy"][c] - cand["per_class_accuracy"][c]
              for c in range(DEPLOYED_CLASS_COUNT) if c != AMSSB]
    drops["G7_worst_other22_drop"] = float(max(deltas))
    drops["G7_worst_other22_idx"] = int(np.argmax(deltas))

    limits = {
        "G1_accuracy": 0.02, "G2_macro_f1": 0.02, "G3_rated_0_20": 0.02,
        "G4_snr0": 0.03, "G5_min_class": 0.05, "G6_amssb_collapse": 0.05,
        "G7_worst_other22_drop": 0.05,
    }
    results = {}
    for k, lim in limits.items():
        results[k] = {"drop": float(drops[k]), "limit": lim,
                      "pass": bool(drops[k] <= lim + 1e-9)}
    results["G8_no_nan_inf"] = {"count": cand["nan_inf_count"],
                                "pass": cand["nan_inf_count"] == 0}
    # G6 also requires the merged AM-SSB not be absolutely collapsed
    results["G6_amssb_collapse"]["amssb_acc"] = cand["amssb_merged_accuracy"]
    results["G6_amssb_collapse"]["pass"] = (results["G6_amssb_collapse"]["pass"]
                                            and cand["amssb_merged_accuracy"] >= 0.5)
    all_pass = all(results[k]["pass"] for k in results)
    return {"name": name, "gates": results, "all_pass": bool(all_pass)}


def main() -> int:
    print("== M29 Phase F2: 23-class merged re-evaluation (read-only) ==")

    # identity fail-closed
    assert sha256_file(CHECKPOINT) == EXPECTED_CHECKPOINT_SHA, "checkpoint SHA"
    assert sha256_file(ONNX) == EXPECTED_ONNX_SHA, "onnx SHA"
    assert_source_order_matches(SOURCE_LABEL_ORDER_24)
    print("  [OK] checkpoint + onnx + source label order identity")

    with np.load(SUBSET, allow_pickle=False) as z:
        sub_indices = z["sub_indices"].astype(np.int64)
        sub_labels = z["sub_labels"].astype(np.int64)
        sub_snrs = z["sub_snrs"].astype(np.float32)
        sub_fp32 = z["sub_fp32"].astype(np.int64)
    n = len(sub_indices)
    print(f"  subset = {n} samples (64/class, validation, NOT test)")

    # FP32 raw logits via ONNX (bit-exact vs PyTorch)
    print("  recomputing FP32 raw logits via ONNX Runtime ...")
    fp32_logits = recompute_fp32_logits(sub_indices)
    fp32_pred24 = fp32_logits.argmax(axis=1).astype(np.int64)
    agree = float((fp32_pred24 == sub_fp32).mean())
    assert agree == 1.0, f"ONNX FP32 argmax drift: agreement={agree}"
    print(f"  [OK] ONNX FP32 argmax == saved sub_fp32 (agreement {agree})")

    candidates = {"fp32": {"logits": fp32_logits, "identity_ok": True}}
    # load + identity-verify the three INT8 candidates
    for name, c in CANDIDATE_MODELS.items():
        assert sha256_file(c["json"]) == c["json_sha"], f"{name} json SHA"
        assert sha256_file(c["raw"]) == c["raw_sha"], f"{name} raw SHA"
        lg = np.load(c["logits"], allow_pickle=False)
        assert lg.shape == (n, 24), f"{name} logits shape {lg.shape}"
        candidates[name] = {"logits": lg.astype(np.float32),
                            "identity_ok": True,
                            "model_json_sha": c["json_sha"],
                            "model_raw_sha": c["raw_sha"]}
        print(f"  [OK] {name}: identity verified, logits {lg.shape} {lg.dtype}")

    # evaluate each candidate
    results = {}
    for name, c in candidates.items():
        results[name] = eval_23(sub_labels, c["logits"], sub_snrs)
        results[name]["identity_ok"] = c["identity_ok"]
        print(f"\n  [{name}] acc={results[name]['accuracy']:.6f} "
              f"macro_f1={results[name]['macro_f1']:.6f} "
              f"min_class={results[name]['min_class_name']} "
              f"({results[name]['min_per_class_accuracy']:.4f}) "
              f"amssb={results[name]['amssb_merged_accuracy']:.4f} "
              f"nan_inf={results[name]['nan_inf_count']}")

    # gates (INT8 vs FP32)
    gates = {}
    passing = []
    for name in CANDIDATE_MODELS:
        g = gate_table(results["fp32"], results[name], name)
        gates[name] = g
        print(f"\n  [gates {name}] all_pass={g['all_pass']}")
        for k, v in g["gates"].items():
            print(f"      {k}: {v}")
        if g["all_pass"]:
            passing.append(name)

    # selection
    selection = {"all_gates_passed": sorted(passing), "result": None, "best": None}
    if not passing:
        selection["result"] = "RML23_MERGED_REJECTED"
    else:
        def key(name):
            r = results[name]
            return (r["min_per_class_accuracy"], r["amssb_merged_accuracy"])
        selection["best"] = max(passing, key=key)
        selection["result"] = f"RML23_MERGED_CANDIDATE_SELECTED={selection['best']}"
    print(f"\n  selection: {json.dumps(selection, ensure_ascii=False)}")

    # top-1 agreement (23-class) for each INT8 vs FP32
    fp32_p = pred_23_from_logits(fp32_logits)
    for name in CANDIDATE_MODELS:
        p = pred_23_from_logits(candidates[name]["logits"])
        results[name]["top1_agreement_23_vs_fp32"] = float((p == fp32_p).mean())
        results[name]["per_class_delta_vs_fp32"] = [
            float(results["fp32"]["per_class_accuracy"][c] - results[name]["per_class_accuracy"][c])
            for c in range(DEPLOYED_CLASS_COUNT)
        ]
    results["fp32"]["top1_agreement_23_vs_fp32"] = 1.0

    out = {
        "phase": "M29-Phase-F2-rml23-merged-evaluation",
        "split": "radioml2018_validation",
        "test_split_touched": False,
        "subset": {"per_class": 64, "size": n, "seed": 2028},
        "source_label_contract_sha256": SOURCE_LABEL_CONTRACT_SHA256,
        "fp32_logits_source": "onnx_runtime_recomputed_bit_exact",
        "candidates": results,
        "gates": gates,
        "selection": selection,
        "merge_algorithm": "logaddexp(logit_AM_SSB_SC, logit_AM_SSB_WC)",
    }
    art = os.path.join(ROOT, "artifacts")
    os.makedirs(art, exist_ok=True)
    with open(os.path.join(art, "m29_rml23_merged_candidate_comparison.json"),
              "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n  wrote m29_rml23_merged_candidate_comparison.json")

    # confusion matrix CSV: one row per (candidate, true_idx) with 23 pred counts
    csv_path = os.path.join(art, "m29_rml23_merged_confusion_matrix.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        header = ["candidate", "true_idx", "true_label"] + [f"pred_{i}" for i in range(23)]
        f.write(",".join(header) + "\n")
        for name in ["fp32"] + list(CANDIDATE_MODELS):
            cm = results[name]["confusion_23"]
            for i in range(23):
                row = [name, str(i), DEPLOYED_LABEL_ORDER_23[i]] + [str(v) for v in cm[i]]
                f.write(",".join(row) + "\n")
    print(f"  wrote m29_rml23_merged_confusion_matrix.csv")
    print("== F2 done ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
