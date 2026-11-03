#!/usr/bin/env python3
"""AM-SSB WC/SC quantization attribution analysis (fix10clean2c pre-review).

Read-only: compares FP32 (onnxruntime) vs host_quantized (bf16, frozen in
deployment_golden/expected_logits_or_argmax.json) raw-24 logits for the SAME
input bytes, then applies the frozen 24->23 logaddexp merge. board_npu is
UNAVAILABLE on this host (no ZG330). Produces a JSON summary for the audit doc.

Run:
    python analyze_amssb.py
"""
import json
import os
import sys
import math
import collections

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
HOST_JSON = os.path.join(ROOT, "deployment_golden", "expected_logits_or_argmax.json")
FP32_DIR = os.path.join(HERE, "fp32")
OUT = os.path.join(HERE, "amssb_attribution.json")

FROZEN_MODEL_RAW_SHA256 = "2425d990dbac0761cfcdb578c2225795e3b700c4afc6800a0b544ff4d50e0cba"
FROZEN_MODEL_JSON_SHA256 = "d43a22848fad56195265fc98f9009039e4e9d9e8da7f58fc5042fb2a602edb2d"

# 24->23 logaddexp merge, matching postprocess/rml23_merged.py exactly.
SOURCE_TO_DEPLOYED = [0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,17,18,19,20,21,22]
AMSSB_WC, AMSSB_SC = 17, 18


def logaddexp(a, b):
    a, b = float(a), float(b)
    if a == float("-inf"):
        return b
    if b == float("-inf"):
        return a
    if a == float("inf") or b == float("inf"):
        return float("inf")
    m = max(a, b)
    return m + math.log1p(math.exp(min(a, b) - m))


def merge_24_to_23(logits24):
    out = [0.0] * 23
    for src in range(24):
        dst = SOURCE_TO_DEPLOYED[src]
        if src == AMSSB_SC:
            out[dst] = logaddexp(out[dst], logits24[src])
        else:
            out[dst] = float(logits24[src])
    return out


def argmax(v):
    return int(max(range(len(v)), key=lambda i: v[i]))


def sha256_file(path):
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    host_doc = json.load(open(HOST_JSON, encoding="utf-8"))
    assert host_doc["model_raw_sha256"] == FROZEN_MODEL_RAW_SHA256, "host model identity mismatch"
    assert host_doc["model_json_sha256"] == FROZEN_MODEL_JSON_SHA256, "host json identity mismatch"

    # host_quantized: key by input_file basename AND input sha
    host_by_index = {}
    for s in host_doc["samples"]:
        host_by_index[s["index"]] = s

    # fp32: key by frame_id (== index)
    fp32_by_index = {}
    for i in range(240):
        p = os.path.join(FP32_DIR, "logits_%d.json" % i)
        r = json.load(open(p, encoding="utf-8"))
        assert r["backend"] == "fp32_onnx", p
        assert r["compiled_model_raw_sha256"] == FROZEN_MODEL_RAW_SHA256, p
        fp32_by_index[i] = r

    # Verify input bytes identical: host records input_file; fp32 records input_sha256.
    # Recompute the sha of each input bin and cross-check fp32.input_sha256 == host input sha.
    mismatches = 0
    for i in range(240):
        h = host_by_index[i]
        inp = os.path.join(ROOT, "deployment_golden", h["input_file"])
        sha = sha256_file(inp)
        if sha != fp32_by_index[i]["input_sha256"]:
            mismatches += 1
    print("input sha mismatches (fp32 vs host):", mismatches)

    # ---- overall (re-verify errata numbers) ----
    diffs_all, coss_all = [], []
    agree23_all = 0
    for i in range(240):
        a = np.array(host_by_index[i]["raw_24_logits"], dtype=np.float64)
        b = np.array(fp32_by_index[i]["raw24"], dtype=np.float64)
        d = np.abs(a - b)
        cos = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-300))
        diffs_all.append(float(d.max()))
        coss_all.append(cos)
        if argmax(merge_24_to_23(a)) == argmax(merge_24_to_23(b)):
            agree23_all += 1
    diffs_all = np.array(diffs_all)
    overall = {
        "n": 240,
        "raw24_max_abs_diff_min": float(diffs_all.min()),
        "raw24_max_abs_diff_median": float(np.median(diffs_all)),
        "raw24_max_abs_diff_max": float(diffs_all.max()),
        "raw24_cosine_min": min(coss_all),
        "raw24_cosine_median": float(np.median(coss_all)),
        "raw24_cosine_max": max(coss_all),
        "merged23_argmax_agree": agree23_all,
        "merged23_argmax_flip": 240 - agree23_all,
    }

    # ---- AM-SSB subset ----
    am = [i for i in range(240) if host_by_index[i]["source_class"] in (AMSSB_WC, AMSSB_SC)]
    rows = []
    stats = collections.Counter()
    prim_counts = collections.Counter()
    stats["n_amssb"] = len(am)
    stats["n_wc"] = sum(1 for i in am if host_by_index[i]["source_class"] == AMSSB_WC)
    stats["n_sc"] = sum(1 for i in am if host_by_index[i]["source_class"] == AMSSB_SC)
    merged23_agree = 0
    merged23_flip = 0

    for i in am:
        h = host_by_index[i]
        src = h["source_class"]
        host_raw = np.array(h["raw_24_logits"], dtype=np.float64)
        fp_raw = np.array(fp32_by_index[i]["raw24"], dtype=np.float64)
        host_top1 = argmax(host_raw)
        fp_top1 = argmax(fp_raw)
        host_merged = merge_24_to_23(host_raw)
        fp_merged = merge_24_to_23(fp_raw)
        host_d23 = argmax(host_merged)
        fp_d23 = argmax(fp_merged)

        # raw24 exact vs AM-family vs other
        def raw_family(t):
            return "WC" if t == 17 else ("SC" if t == 18 else "OTHER")

        fp_exact_correct = (fp_top1 == src)
        host_exact_correct = (host_top1 == src)
        fp_am_correct = fp_top1 in (17, 18)
        host_am_correct = host_top1 in (17, 18)
        fp_d23_correct = (fp_d23 == 17)
        host_d23_correct = (host_d23 == 17)

        # WC<->SC flip within AM family
        fp_family = raw_family(fp_top1)
        host_family = raw_family(host_top1)
        wc_sc_swap = (fp_top1 in (17, 18)) and (host_top1 in (17, 18)) and (fp_top1 != host_top1)

        # raw24 WC/SC internal logit gap
        def gap(raw):
            return float(raw[17] - raw[18])
        fp_gap, host_gap = gap(fp_raw), gap(host_raw)

        # raw24 margin (top1 - top2)
        def margin(raw):
            s = sorted(float(v) for v in raw)
            return s[-1] - s[-2]
        fp_margin, host_margin = margin(fp_raw), margin(host_raw)

        # deployed23 AM-SSB margin vs next best
        def d23_margin(merged):
            s = sorted(float(v) for v in merged)
            return s[-1] - s[-2]
        fp_d23m, host_d23m = d23_margin(fp_merged), d23_margin(host_merged)

        d = np.abs(host_raw - fp_raw)
        cos = float(np.dot(host_raw, fp_raw) / (np.linalg.norm(host_raw) * np.linalg.norm(fp_raw) + 1e-300))

        # attribution (primary, precedence order per task book §5)
        if not fp_exact_correct:
            if fp_family in ("WC", "SC"):
                prim = "FP32_MODEL_CONFUSION_AMSSB_INTERNAL"
            else:
                prim = "FP32_MODEL_CONFUSION_OTHER"
        elif fp_exact_correct and not host_exact_correct:
            prim = "HOST_QUANTIZATION_FLIP"
        elif fp_exact_correct and host_exact_correct:
            prim = "BACKENDS_AGREE_CORRECT"
        else:
            prim = "OTHER"
        # software-merge-only: raw24 wrong/differing in either backend but deployed23 correct in both
        merge_only = (fp_d23_correct and host_d23_correct and (not fp_exact_correct or not host_exact_correct))
        prim_counts[prim] += 1
        stats["FP32_MODEL_CONFUSION"] += (0 if fp_exact_correct else 1)
        stats["FP32_MODEL_CONFUSION_AMSSB_INTERNAL"] += (0 if fp_exact_correct else (1 if fp_family in ("WC", "SC") else 0))
        stats["FP32_MODEL_CONFUSION_OTHER"] += (0 if fp_exact_correct else (0 if fp_family in ("WC", "SC") else 1))
        stats["HOST_QUANTIZATION_FLIP"] += (1 if (fp_exact_correct and not host_exact_correct) else 0)
        stats["HOST_QUANTIZATION_RESCUE"] += (1 if ((not fp_exact_correct) and host_exact_correct) else 0)
        stats["WC_SC_RAW_SWAP"] += (1 if wc_sc_swap else 0)
        stats["SOFTWARE_MERGE_ONLY"] += (1 if merge_only else 0)
        stats["FP32_DEPLOYED23_CORRECT"] += (1 if fp_d23_correct else 0)
        stats["HOST_DEPLOYED23_CORRECT"] += (1 if host_d23_correct else 0)
        # fp32 WC->SC / SC->WC raw24 flips (internal AM-SSB family confusion)
        if src == AMSSB_WC and fp_top1 == AMSSB_SC:
            stats["FP32_WC_TO_SC"] += 1
        if src == AMSSB_SC and fp_top1 == AMSSB_WC:
            stats["FP32_SC_TO_WC"] += 1
        if src == AMSSB_WC and host_top1 == AMSSB_SC:
            stats["HOST_WC_TO_SC"] += 1
        if src == AMSSB_SC and host_top1 == AMSSB_WC:
            stats["HOST_SC_TO_WC"] += 1
        # merged-23 argmax agreement (fp32 vs host) on this AM frame
        if fp_d23 == host_d23:
            merged23_agree += 1
        else:
            merged23_flip += 1

        rows.append({
            "index": i,
            "source_class": src,
            "source_label": h["source_label"],
            "snr_db": h["snr_db"],
            "fp32_raw24_top1": fp_top1,
            "fp32_raw24_family": fp_family,
            "host_raw24_top1": host_top1,
            "host_raw24_family": host_family,
            "fp32_raw24_exact_correct": fp_exact_correct,
            "host_raw24_exact_correct": host_exact_correct,
            "fp32_raw24_am_correct": fp_am_correct,
            "host_raw24_am_correct": host_am_correct,
            "fp32_deployed23_top1": fp_d23,
            "host_deployed23_top1": host_d23,
            "fp32_deployed23_correct": fp_d23_correct,
            "host_deployed23_correct": host_d23_correct,
            "raw24_max_abs_diff": float(d.max()),
            "raw24_cosine": cos,
            "fp32_logit_gap_17_18": fp_gap,
            "host_logit_gap_17_18": host_gap,
            "fp32_raw24_margin": fp_margin,
            "host_raw24_margin": host_margin,
            "fp32_deployed23_margin": fp_d23m,
            "host_deployed23_margin": host_d23m,
            "wc_sc_raw_swap": wc_sc_swap,
            "primary_attribution": prim,
        })

    out = {
        "overall": overall,
        "amssb": {
            "merged23_argmax_agree": merged23_agree,
            "merged23_argmax_flip": merged23_flip,
            "stats": dict(sorted(stats.items())),
            "primary_attribution_counts": dict(sorted(prim_counts.items())),
            "per_sample": rows,
        },
    }
    json.dump(out, open(OUT, "w", encoding="utf-8"), indent=2, ensure_ascii=False)

    # ---- human-readable summary ----
    print("=== OVERALL (fp32 vs host_quantized, 240 frames) ===")
    for k, v in overall.items():
        print("  %s = %s" % (k, v))
    print()
    print("=== AM-SSB subset (%d frames: %d WC + %d SC) ===" % (stats["n_amssb"], stats["n_wc"], stats["n_sc"]))
    print("  FP32_MODEL_CONFUSION (fp32 raw24 top1 != source): %d" % stats["FP32_MODEL_CONFUSION"])
    print("    - internal AM-SSB (WC<->SC): %d" % stats["FP32_MODEL_CONFUSION_AMSSB_INTERNAL"])
    print("    - to OTHER class:            %d" % stats["FP32_MODEL_CONFUSION_OTHER"])
    print("  HOST_QUANTIZATION_FLIP (fp32 correct, host wrong): %d" % stats["HOST_QUANTIZATION_FLIP"])
    print("  HOST_QUANTIZATION_RESCUE (fp32 wrong, host correct): %d" % stats["HOST_QUANTIZATION_RESCUE"])
    print("  FP32_WC_TO_SC=%d  FP32_SC_TO_WC=%d  HOST_WC_TO_SC=%d  HOST_SC_TO_WC=%d" % (
        stats["FP32_WC_TO_SC"], stats["FP32_SC_TO_WC"], stats["HOST_WC_TO_SC"], stats["HOST_SC_TO_WC"]))
    print("  WC_SC_RAW_SWAP (both in AM family, fp32 != host): %d" % stats["WC_SC_RAW_SWAP"])
    print("  SOFTWARE_MERGE_ONLY (raw24 wrong/differing but deployed23 both correct): %d" % stats["SOFTWARE_MERGE_ONLY"])
    print("  FP32_DEPLOYED23_CORRECT: %d / HOST_DEPLOYED23_CORRECT: %d" % (stats["FP32_DEPLOYED23_CORRECT"], stats["HOST_DEPLOYED23_CORRECT"]))
    print("  merged-23 argmax agree (fp32 vs host): %d / flip: %d" % (merged23_agree, merged23_flip))
    print("  primary attribution counts:", dict(sorted(prim_counts.items())))
    print()
    print("=== per-sample table ===")
    hdr = ("idx src snr  fp_top1 fp_fam  host_top1 host_fam  fpExact hostExact "
           "fpD23 hostD23  maxAbs  cos    fpGap17_18 hostGap17_18  fpMargin hostMargin  attrib")
    print(hdr)
    for r in rows:
        print(("  %3d  %2d %5.1f  %2d %-5s  %2d %-8s  %s      %s       "
               "%2d   %2d    %.4f  %.4f  %+.3f   %+.3f   %.3f  %.3f  %s")
              % (r["index"], r["source_class"], r["snr_db"],
                 r["fp32_raw24_top1"], r["fp32_raw24_family"],
                 r["host_raw24_top1"], r["host_raw24_family"],
                 "T" if r["fp32_raw24_exact_correct"] else "F",
                 "T" if r["host_raw24_exact_correct"] else "F",
                 r["fp32_deployed23_top1"], r["host_deployed23_top1"],
                 r["raw24_max_abs_diff"], r["raw24_cosine"],
                 r["fp32_logit_gap_17_18"], r["host_logit_gap_17_18"],
                 r["fp32_raw24_margin"], r["host_raw24_margin"],
                 r["primary_attribution"]))
    print()
    print("wrote", OUT)


if __name__ == "__main__":
    main()
