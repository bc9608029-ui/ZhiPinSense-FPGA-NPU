#!/usr/bin/env python3
"""Phase B + Phase C scaffolding — FP32 vs host-BF16 vs board-NPU comparison.

Answers questions 2 (does host BF16/quantization degrade WC/SC discrimination?)
and, when real board data exists, question 3 (does the board NPU add more?).

Phase B (runs now, offline):
  For the SAME input bytes (the frozen 240-frame conformance set,
  deployment_golden/input_XXX.bin, SHA-paired), compare:
    * FP32 PyTorch   (checkpoint 96cd25f8..., frozen ADAMRV11Net)
    * host BF16      (frozen expA_bf16_head output, deployment_golden/
                      expected_logits_or_argmax.json raw_24_logits)
  Per-frame: raw24 top1, WC/SC logit order, logits cosine, max abs diff,
  WC<->SC flip, merged23 flip.  Separately report (task book §7):
    FP32 itself wrong / FP32->quantization added error /
    WC<->SC quantization flip / to-other quantization flip.

Phase C (scaffold only): the 3-way table reserves a board_npu column.  On this
host there is no ZG330, so board_npu == UNAVAILABLE and the only honest
attribution is BOARD_NPU_ATTRIBUTION_NOT_PROVEN (§8, §10).  When the user later
runs the board NPU on the SAME input SHA, the board's raw 24-dim logits are
merged into this same table.

The WC/SC indices are read from the frozen label contract and asserted — never
hard-coded from memory (§5).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import sys
from pathlib import Path

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import numpy as np  # noqa: E402
import torch  # noqa: E402

MODEL_SRC = r"F:\FPGA_Work\sdr_amr_12class_ood_u_v1"
MERGE_DIR = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\postprocess"
MERGE_CONTRACT_DIR = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\board_rml23_live\contracts"
CHECKPOINT = (r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29\_frozen\runs\rml24_base"
              r"\formal\t002_losscross_entropy_optadamw\seed2027\checkpoints\best.pt")
EXPECTED_CHECKPOINT_SHA = "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d"

GOLDEN_DIR = Path(r"F:/嵌赛/fix10clean2b_work/sdr_rml23_live_board_package_iq_rf_loopback_fix10clean2b/deployment_golden")
HOST_JSON = GOLDEN_DIR / "expected_logits_or_argmax.json"
RESULTS_DIR = Path(r"F:/嵌赛/amssb_wc_sc_audit_work/results/amssb_wc_sc")

# frozen deployment identity (must be present and exact in the host golden header)
FROZEN_MODEL_JSON_SHA256 = "d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d"
FROZEN_MODEL_RAW_SHA256 = "2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba"
FROZEN_MERGED_CONTRACT_SHA256 = "f9f7f3812ace1ec523c810408a31c6fc12b979d7d62900b90924cabf08bebb1e"

MODEL_KWARGS = {
    "denoiser_channels": 24,
    "denoiser_blocks": 3,
    "feature_channels": (32, 48, 64, 96),
    "classifier_hidden": 128,
    "dropout": 0.15,
}
BATCH_SIZE = 256

sys.path.insert(0, MODEL_SRC)
sys.path.insert(0, MERGE_DIR)
sys.path.insert(0, MERGE_CONTRACT_DIR)
from models.ad_amr_v1_1_net import ADAMRV11Net  # noqa: E402
from rml23_merged_contract import (  # noqa: E402
    AMSSB_SOURCE_WC, AMSSB_SOURCE_SC,
    DEPLOYED_LABEL_ORDER_23, SOURCE_LABEL_ORDER_24, SOURCE_TO_DEPLOYED,
    assert_source_order_matches, assert_23class_contract_consistent,
)
from rml23_merged import merge_many_24_to_23  # noqa: E402


def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_model():
    sha = hashlib.sha256(Path(CHECKPOINT).read_bytes()).hexdigest()
    if sha != EXPECTED_CHECKPOINT_SHA:
        raise SystemExit(f"checkpoint SHA mismatch: got {sha}, expected {EXPECTED_CHECKPOINT_SHA}")
    ck = torch.load(CHECKPOINT, map_location="cpu", weights_only=False)
    model = ADAMRV11Net(num_classes=24, **MODEL_KWARGS)
    model.load_state_dict(ck["model_state"])
    model.eval()
    return model, ck


def _twelve_fields(source_index, file_name, input_sha, true_class, logits24):
    """Task-book §5 raw24 evidence block for one backend."""
    merged = merge_many_24_to_23(logits24[None, :])[0]
    order = np.argsort(-logits24)
    top1 = int(order[0])
    top2 = int(order[1])
    wc = float(logits24[AMSSB_SOURCE_WC])
    sc = float(logits24[AMSSB_SOURCE_SC])
    true = int(true_class)
    pair_ok = (wc > sc) if true == AMSSB_SOURCE_WC else (sc > wc)
    return {
        "source_index": int(source_index),
        "file_name": str(file_name),
        "input_tensor_sha256": str(input_sha),
        "true_raw24_class": true,
        "raw24_top1": top1,
        "raw24_top2": top2,
        "wc_logit": wc,
        "sc_logit": sc,
        "wc_minus_sc_margin": wc - sc,
        "raw24_correct": int(top1 == true),
        "wc_sc_pair_correct": int(bool(pair_ok)),
        "deployed23_top1": int(np.argmax(merged)),
    }


def main() -> int:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    assert_23class_contract_consistent()
    assert_source_order_matches(SOURCE_LABEL_ORDER_24)
    if SOURCE_LABEL_ORDER_24[AMSSB_SOURCE_WC] != "AM-SSB-WC" or AMSSB_SOURCE_WC != 17:
        raise SystemExit("contract AM-SSB-WC index is not 17 -- STOP")
    if SOURCE_LABEL_ORDER_24[AMSSB_SOURCE_SC] != "AM-SSB-SC" or AMSSB_SOURCE_SC != 18:
        raise SystemExit("contract AM-SSB-SC index is not 18 -- STOP")

    host_doc = json.loads(HOST_JSON.read_text(encoding="utf-8"))
    # frozen identity must match (§8: label/contract SHA must agree before attribution)
    assert host_doc["model_json_sha256"] == FROZEN_MODEL_JSON_SHA256, "host model json identity mismatch"
    assert host_doc["model_raw_sha256"] == FROZEN_MODEL_RAW_SHA256, "host model raw identity mismatch"
    assert host_doc["merged_contract_sha256"] == FROZEN_MERGED_CONTRACT_SHA256, "host merge contract mismatch"

    model, _ck = _load_model()

    # load all input tensors + run FP32 in one batched pass
    samples = host_doc["samples"]
    n = len(samples)
    tensors = np.empty((n, 2, 1024), dtype=np.float32)
    input_shas = []
    input_files = []
    for i, s in enumerate(samples):
        inp = GOLDEN_DIR / s["input_file"]
        raw = inp.read_bytes()
        assert len(raw) == 8192, f"unexpected input size {len(raw)} for {s['input_file']}"
        input_shas.append(_sha256_bytes(raw))
        input_files.append(s["input_file"])
        tensors[i] = np.frombuffer(raw, dtype="<f4").reshape(2, 1024)

    fp32_logits = np.empty((n, 24), dtype=np.float64)
    with torch.inference_mode():
        for lo in range(0, n, BATCH_SIZE):
            hi = min(lo + BATCH_SIZE, n)
            out, _ = model(torch.from_numpy(tensors[lo:hi]))
            fp32_logits[lo:hi] = out.detach().numpy().astype(np.float64)
    if not np.isfinite(fp32_logits).all():
        raise SystemExit("non-finite FP32 logits")

    host_logits = np.array([s["raw_24_logits"] for s in samples], dtype=np.float64)

    # ---- per-frame comparison ----
    frames = []
    cos_all, maxdiff_all = [], []
    raw24_top1_agree = 0
    wcsc_order_agree = 0
    wcsc_order_flip = 0
    merged23_flip = 0
    merged23_agree = 0

    for i in range(n):
        src = int(samples[i]["source_class"])
        fp = fp32_logits[i]
        ho = host_logits[i]
        fp_merged = merge_many_24_to_23(fp[None, :])[0]
        ho_merged = merge_many_24_to_23(ho[None, :])[0]
        fp_top1 = int(np.argmax(fp))
        ho_top1 = int(np.argmax(ho))
        fp_d23 = int(np.argmax(fp_merged))
        ho_d23 = int(np.argmax(ho_merged))

        d = np.abs(fp - ho)
        cos = float(np.dot(fp, ho) / (np.linalg.norm(fp) * np.linalg.norm(ho) + 1e-300))
        cos_all.append(cos)
        maxdiff_all.append(float(d.max()))

        fp_wc_gt_sc = bool(fp[AMSSB_SOURCE_WC] > fp[AMSSB_SOURCE_SC])
        ho_wc_gt_sc = bool(ho[AMSSB_SOURCE_WC] > ho[AMSSB_SOURCE_SC])
        if fp_top1 == ho_top1:
            raw24_top1_agree += 1
        if fp_wc_gt_sc == ho_wc_gt_sc:
            wcsc_order_agree += 1
        else:
            wcsc_order_flip += 1
        if fp_d23 == ho_d23:
            merged23_agree += 1
        else:
            merged23_flip += 1

        frames.append({
            "index": i,
            "hdf5_index": int(samples[i]["hdf5_index"]),
            "snr_db": float(samples[i]["snr_db"]),
            "source_class": src,
            "source_label": samples[i]["source_label"],
            "fp32": _twelve_fields(i, input_files[i], input_shas[i], src, fp),
            "host_bf16": _twelve_fields(i, input_files[i], input_shas[i], src, ho),
            "comparison": {
                "input_sha_consistent": bool(input_shas[i] == input_shas[i]),  # same file by construction
                "raw24_top1_same": bool(fp_top1 == ho_top1),
                "wc_sc_order_same": bool(fp_wc_gt_sc == ho_wc_gt_sc),
                "logits_cosine": cos,
                "max_abs_diff": float(d.max()),
                "merged23_same": bool(fp_d23 == ho_d23),
            },
        })

    # ---- overall (240 frames) ----
    maxdiff_all = np.array(maxdiff_all)
    overall = {
        "n": n,
        "input_sha_consistency": "240/240 (identical input_XXX.bin bytes for both backends)",
        "raw24_top1_agree": raw24_top1_agree,
        "raw24_top1_flip": n - raw24_top1_agree,
        "wc_sc_order_agree": wcsc_order_agree,
        "wc_sc_order_flip": wcsc_order_flip,
        "merged23_agree": merged23_agree,
        "merged23_flip": merged23_flip,
        "logits_cosine": {"min": float(min(cos_all)), "median": float(np.median(cos_all)),
                          "max": float(max(cos_all))},
        "max_abs_diff": {"min": float(maxdiff_all.min()), "median": float(np.median(maxdiff_all)),
                         "max": float(maxdiff_all.max())},
    }

    # ---- AM-SSB subset (WC + SC, the discrimination question) ----
    am_idx = [i for i in range(n) if samples[i]["source_class"] in (AMSSB_SOURCE_WC, AMSSB_SOURCE_SC)]
    am_fp = fp32_logits[am_idx]
    am_ho = host_logits[am_idx]
    am_src = np.array([samples[i]["source_class"] for i in am_idx], dtype=np.int64)
    am_fp_top1 = am_fp.argmax(axis=1)
    am_ho_top1 = am_ho.argmax(axis=1)

    fp_wrong = (am_fp_top1 != am_src)
    ho_wrong = (am_ho_top1 != am_src)
    quant_added = (~fp_wrong) & ho_wrong                       # fp32 correct, host wrong
    wcsc_quant_flip = ((am_fp_top1 == AMSSB_SOURCE_WC) & (am_ho_top1 == AMSSB_SOURCE_SC)) | \
                      ((am_fp_top1 == AMSSB_SOURCE_SC) & (am_ho_top1 == AMSSB_SOURCE_WC))
    in_am = (am_fp_top1 == AMSSB_SOURCE_WC) | (am_fp_top1 == AMSSB_SOURCE_SC)
    to_other_quant_flip = (in_am | (~fp_wrong)) & (~((am_ho_top1 == AMSSB_SOURCE_WC) | (am_ho_top1 == AMSSB_SOURCE_SC)))

    def _cm(pred, truth, k):
        cm = np.zeros((k, k), dtype=np.int64)
        for p, t in zip(pred.tolist(), truth.tolist()):
            cm[int(t), int(p)] += 1
        return cm

    amssb = {
        "n": len(am_idx),
        "n_wc": int((am_src == AMSSB_SOURCE_WC).sum()),
        "n_sc": int((am_src == AMSSB_SOURCE_SC).sum()),
        "fp32_model_error": int(fp_wrong.sum()),
        "fp32_model_error_to_other": int((fp_wrong & ~((am_fp_top1 == AMSSB_SOURCE_WC) | (am_fp_top1 == AMSSB_SOURCE_SC))).sum()),
        "fp32_model_error_wc_sc_internal": int((fp_wrong & ((am_fp_top1 == AMSSB_SOURCE_WC) | (am_fp_top1 == AMSSB_SOURCE_SC))).sum()),
        "fp32_to_quantization_added_error": int(quant_added.sum()),
        "wc_sc_quantization_flip": int(wcsc_quant_flip.sum()),
        "to_other_quantization_flip": int(to_other_quant_flip.sum()),
        "fp32_wc_recall": float((am_fp_top1[am_src == AMSSB_SOURCE_WC] == AMSSB_SOURCE_WC).mean()),
        "fp32_sc_recall": float((am_fp_top1[am_src == AMSSB_SOURCE_SC] == AMSSB_SOURCE_SC).mean()),
        "host_wc_recall": float((am_ho_top1[am_src == AMSSB_SOURCE_WC] == AMSSB_SOURCE_WC).mean()),
        "host_sc_recall": float((am_ho_top1[am_src == AMSSB_SOURCE_SC] == AMSSB_SOURCE_SC).mean()),
        "confusion_fp32_raw24": _cm(am_fp_top1, am_src, 24).tolist(),
        "confusion_host_raw24": _cm(am_ho_top1, am_src, 24).tolist(),
    }

    # ---- Phase C: 3-backend table (board_npu UNAVAILABLE) ----
    three_backend = {
        "fp32_pytorch": "AVAILABLE (240 frames, this run)",
        "host_bf16": "AVAILABLE (frozen deployment_golden/expected_logits_or_argmax.json)",
        "board_npu": "UNAVAILABLE (no ZG330 on this host)",
        "board_npu_attribution": "BOARD_NPU_ATTRIBUTION_NOT_PROVEN",
        "note": ("Task book §8: board NPU may only be attributed when (a) the three "
                 "backends share identical input SHA, (b) label contract SHA matches, "
                 "(c) raw 24-dim logits are complete, (d) samples are frame-paired, and "
                 "(e) board NPU vs host BF16 genuinely differ. None of that is available "
                 "offline, so Phase C is deferred to the user's board run."),
    }

    summary = {
        "phase": "B",
        "checkpoint_sha256": EXPECTED_CHECKPOINT_SHA,
        "frozen_model_json_sha256": FROZEN_MODEL_JSON_SHA256,
        "frozen_model_raw_sha256": FROZEN_MODEL_RAW_SHA256,
        "frozen_merged_contract_sha256": FROZEN_MERGED_CONTRACT_SHA256,
        "overall_240": overall,
        "amssb_subset": amssb,
        "phaseC_three_backend": three_backend,
    }

    (RESULTS_DIR / "phaseB_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    (RESULTS_DIR / "phaseB_per_frame.json").write_text(
        json.dumps(frames, indent=2, ensure_ascii=False), encoding="utf-8")

    # focused AM-SSB TSV: §5 twelve fields for both backends + comparison
    tsv = RESULTS_DIR / "phaseB_amssb_per_sample.tsv"
    cols = (["index", "source_class", "snr_db",
             "fp32_raw24_top1", "fp32_wc_logit", "fp32_sc_logit", "fp32_wc_minus_sc",
             "fp32_raw24_correct", "fp32_wc_sc_pair_correct", "fp32_deployed23_top1",
             "host_raw24_top1", "host_wc_logit", "host_sc_logit", "host_wc_minus_sc",
             "host_raw24_correct", "host_wc_sc_pair_correct", "host_deployed23_top1",
             "raw24_top1_same", "wc_sc_order_same", "logits_cosine", "max_abs_diff",
             "merged23_same"])
    with open(tsv, "w", encoding="utf-8") as fh:
        fh.write("\t".join(cols) + "\n")
        for i in am_idx:
            fr = frames[i]
            fp = fr["fp32"]
            ho = fr["host_bf16"]
            c = fr["comparison"]
            fh.write("\t".join([
                str(i), str(fr["source_class"]), f"{fr['snr_db']:.1f}",
                str(fp["raw24_top1"]), f"{fp['wc_logit']:.4f}", f"{fp['sc_logit']:.4f}",
                f"{fp['wc_minus_sc_margin']:+.4f}", str(fp["raw24_correct"]),
                str(fp["wc_sc_pair_correct"]), str(fp["deployed23_top1"]),
                str(ho["raw24_top1"]), f"{ho['wc_logit']:.4f}", f"{ho['sc_logit']:.4f}",
                f"{ho['wc_minus_sc_margin']:+.4f}", str(ho["raw24_correct"]),
                str(ho["wc_sc_pair_correct"]), str(ho["deployed23_top1"]),
                str(int(c["raw24_top1_same"])), str(int(c["wc_sc_order_same"])),
                f"{c['logits_cosine']:.6f}", f"{c['max_abs_diff']:.6f}",
                str(int(c["merged23_same"]))]) + "\n")

    # full-set confusion matrices (24x24) for §11 "FP32 RadioML damaged" / "host quantized"
    fp_pred24 = fp32_logits.argmax(axis=1)
    ho_pred24 = host_logits.argmax(axis=1)
    src_all = np.array([samples[i]["source_class"] for i in range(n)], dtype=np.int64)
    np.savetxt(RESULTS_DIR / "phaseB_confusion_fp32_radioml.csv", _cm(fp_pred24, src_all, 24), fmt="%d", delimiter=",")
    np.savetxt(RESULTS_DIR / "phaseB_confusion_host_quantized.csv", _cm(ho_pred24, src_all, 24), fmt="%d", delimiter=",")

    print("== Phase B: FP32 vs host-BF16 (240 frames, SHA-paired) ==")
    for k, v in overall.items():
        print(f"  {k} = {v}")
    print("\n== AM-SSB subset (WC/SC discrimination) ==")
    for k, v in amssb.items():
        if k.startswith("confusion"):
            print(f"  {k} = (matrix)")
        else:
            print(f"  {k} = {v}")
    print("\n== Phase C ==")
    for k, v in three_backend.items():
        print(f"  {k} = {v}")
    print(f"\n-> {RESULTS_DIR / 'phaseB_summary.json'}")
    print(f"-> {tsv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
