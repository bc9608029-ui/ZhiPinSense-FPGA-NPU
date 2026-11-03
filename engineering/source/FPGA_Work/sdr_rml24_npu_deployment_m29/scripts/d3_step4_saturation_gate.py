#!/usr/bin/env python
"""M29 Phase D.3 Step 4 — per-class saturation (new model) + gate verdict.

Reads the NEW quantized model's input-layer + first-conv scales, recomputes
per-class INPUT saturation on the fixed 1536 diagnostic subset with the NEW
clip range, loads the dra384 icraft-run report, and prints a gate verdict vs
the frozen 384 baseline + expA numbers.

READ-ONLY: no test, no board.  Writes work/d3_step4_saturation_gate.json.
"""
from __future__ import annotations

import json
import os
import sys

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import h5py  # noqa: E402
import numpy as np  # noqa: E402

ROOT = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29"
HDF5_PATH = r"F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5"
SUBSET = os.path.join(ROOT, "work", "eval_full", "subset_index.npz")
DRA_QJSON = r"F:\FPGA_Work\_tmp_24class_dra_384_20261011\jsonraw\model_24class_quantized.json"
DRA_EVAL = r"F:\FPGA_Work\_tmp_24class_dra_384_20261011_eval_result\dra384_report.json"

LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)

# frozen 384-baseline (all-int8) 1536-subset icraft-run numbers (memory/doc)
BASELINE_384 = {
    "acc": 0.539062, "fp32_acc": 0.554036,
    "macro_f1": 0.5619, "rated_0_20": 0.8385,
    "min_class": 0.0781, "min_class_name": "AM-SSB-SC",
    "am_ssb_sc_correct_rate": 0.078, "am_ssb_sc_fp32": 0.516,
    "top1_agree": 0.615,
}
EXPA = {"am_ssb_sc_correct_rate": 0.203, "min_class": 0.203125, "top1_agree": 0.810}


def parse_scales(s: str):
    if not isinstance(s, str) or "scales" not in s:
        return None
    body = s.split("]", 1)[1].replace(")", "").replace("(", "")
    parts = [p for p in body.split(",") if p.strip()]
    out = []
    for p in parts:
        p = p.strip()
        if "*" in p:
            n, v = p.split("*")
            out.extend([float(v)] * int(n))
        else:
            out.append(float(p))
    return out


def edt(x):
    d = x.get("dtype", {})
    if isinstance(d, dict):
        e = d.get("element_dtype")
        if isinstance(e, dict):
            return e
    return None


def main() -> int:
    print("== M29 Phase D.3 Step 4: per-class saturation (new model) + gate ==")

    with open(DRA_QJSON, "r", encoding="utf-8") as f:
        qj = json.load(f)
    convs = [o for o in qj["ops"] if o["_type_key"] == "icraft::xir::Conv2d"]
    first_conv = min(convs, key=lambda o: o["op_id"])
    conv_in_q = edt(first_conv["inputs"][0])
    conv_out_q = edt(first_conv["outputs"][0])
    new_in_scale = parse_scales(conv_in_q.get("scale", ""))
    new_out_scale = parse_scales(conv_out_q.get("scale", ""))
    new_clip = 127.0 * new_in_scale[0]
    old_in_scale = 0.052646082
    old_clip = 127.0 * old_in_scale
    print(f"  OLD input scale {old_in_scale:.9f} -> clip +/-{old_clip:.6f}")
    print(f"  NEW input scale {new_in_scale} -> clip +/-{new_clip:.6f}")
    print(f"  NEW stem-out scale[0] {new_out_scale[0]:.9f} -> clip +/-{127.0*new_out_scale[0]:.6f}")

    sub = np.load(SUBSET, allow_pickle=False)
    sub_indices = sub["sub_indices"].astype(np.int64)
    sub_labels = sub["sub_labels"].astype(np.int64)

    per_class = {}
    with h5py.File(HDF5_PATH, "r") as f:
        X = f["X"]
        for label in range(24):
            pos = np.flatnonzero(sub_labels == label)
            sat_old, sat_new = [], []
            for p in pos:
                planar = np.ascontiguousarray(np.asarray(X[int(sub_indices[p])], dtype=np.float32).T)
                sat_old.append(float(np.mean(np.abs(planar) > old_clip)))
                sat_new.append(float(np.mean(np.abs(planar) > new_clip)))
            per_class[label] = {
                "class": LABEL_ORDER_24[label],
                "input_sat_old_mean": float(np.mean(sat_old)),
                "input_sat_new_mean": float(np.mean(sat_new)),
                "input_sat_new_max": float(np.max(sat_new)),
            }

    print(f"\n  {'class':12s} {'oldSat%':>8s} {'newSat%':>8s} {'newSatMax%':>10s}")
    for l in range(24):
        c = per_class[l]
        flag = " <== AM" if l in (17, 18) else ""
        print(f"  {c['class']:12s} {c['input_sat_old_mean']*100:8.3f} "
              f"{c['input_sat_new_mean']*100:8.3f} {c['input_sat_new_max']*100:10.3f}{flag}")

    # ---- dra384 eval report ----
    gate = {}
    if os.path.isfile(DRA_EVAL):
        with open(DRA_EVAL, "r", encoding="utf-8") as f:
            rep = json.load(f)
        q = rep["quantized"]; fp = rep["fp32_on_same_subset"]
        conf = rep["am_ssb_sc_confusion"]
        gate = {
            "acc": q["accuracy"], "fp32_acc": fp["accuracy"],
            "acc_drop": rep["accuracy_drop"],
            "macro_f1": q["macro_f1"], "rated_0_20": q["rated_0_20_accuracy"],
            "min_class": q["min_per_class_accuracy"], "min_class_name": q["min_class_name"],
            "min_class_drop": rep["min_class_drop"],
            "am_ssb_sc_correct_rate": conf["correct_rate"],
            "am_ssb_sc_high_snr": conf["high_snr_12_30"]["correct_rate"],
            "am_ssb_sc_fp32": fp["per_class_accuracy"][18],
            "top1_agree": rep["top1_agreement_quant_vs_fp32"],
        }
        print(f"\n  dra384 quantized: acc={q['accuracy']:.6f} (fp32 {fp['accuracy']:.6f})")
        print(f"  min_class={q['min_per_class_accuracy']:.4f} {q['min_class_name']}")
        print(f"  AM-SSB-SC acc={conf['correct_rate']:.4f} (fp32 {fp['per_class_accuracy'][18]:.4f}) "
              f" 12-30dB={conf['high_snr_12_30']['correct_rate']:.4f}")
        print(f"  Top-1 agree={rep['top1_agreement_quant_vs_fp32']:.4f}")
        print(f"  vs baseline384 min_class {BASELINE_384['min_class']:.4f} / "
              f"AM-SSB-SC {BASELINE_384['am_ssb_sc_correct_rate']:.3f} / agree {BASELINE_384['top1_agree']:.3f}")
    else:
        print(f"\n  [WARN] dra384 report not found: {DRA_EVAL}")

    out = {
        "phase": "M29-Phase-D3-Step4-saturation-gate",
        "old_input_scale": old_in_scale, "old_input_clip": old_clip,
        "new_input_scale": new_in_scale, "new_input_clip": new_clip,
        "new_stem_out_scale0": new_out_scale[0],
        "per_class_input_saturation": [per_class[l] for l in range(24)],
        "dra384_eval": gate,
        "baseline_384": BASELINE_384, "expA": EXPA,
    }
    osp = os.path.join(ROOT, "work", "d3_step4_saturation_gate.json")
    with open(osp, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2)
    print(f"\n== wrote {osp} ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
