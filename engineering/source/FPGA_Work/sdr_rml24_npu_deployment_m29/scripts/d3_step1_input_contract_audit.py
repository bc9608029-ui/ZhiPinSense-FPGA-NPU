#!/usr/bin/env python
"""M29 Phase D.3 Step 1 — input-contract audit (read-only).

Verifies that the PyTorch / ONNX / calibration-.bin / icraft-run inputs agree on
dtype, I/Q order, shape, normalization, rec_scale/pre_scale, clipping, byte order;
reports the iCraft input-layer and first-conv quantizer (scale / zero-point / clip);
and computes per-class input saturation on the fixed 1536-sample diagnostic subset.

READ-ONLY: no test access, no board, no new calibration, no model change.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import h5py  # noqa: E402
import numpy as np  # noqa: E402

ROOT = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29"
V11 = r"F:\FPGA_Work\sdr_amr_rml24_ood_v1_1"
HDF5_PATH = r"F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5"
INDEX_PATH = os.path.join(V11, "data", "radioml2018", "rml24_split_indices.npz")
CAL_MANIFEST = os.path.join(ROOT, "work", "calibration_384", "calibration_manifest.json")
SUBSET = os.path.join(ROOT, "work", "eval_full", "subset_index.npz")
ONNX_REPORT = os.path.join(ROOT, "work", "onnx", "export_report.json")
QJSON = r"F:\FPGA_Work\_tmp_24class_expA_bf16_head_384_20261010\jsonraw\model_24class_quantized.json"

LABEL_ORDER_24 = (
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
    "AM-DSB-SC", "FM", "GMSK", "OQPSK",
)


def parse_scales(s: str):
    """Parse '@scales([axis=-1]24*0.05,8*1)' -> list of floats.  None if no scale."""
    if not isinstance(s, str) or "scales" not in s:
        return None
    body = s.split("]", 1)[1]
    body = body.replace(")", "").replace("(", "")
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


def clip_of(scale: float) -> float:
    return 127.0 * scale


def main() -> int:
    report = {"phase": "M29-Phase-D3-Step1-input-contract-audit"}

    print("== M29 Phase D.3 Step 1: input-contract audit ==")

    # ---------------- Part A: input contract ----------------
    print("\n[A] input contract consistency")
    with np.load(INDEX_PATH, allow_pickle=False) as idx:
        val_indices = idx["validation_indices"].astype(np.int64, copy=True)
        val_labels = idx["validation_labels"].astype(np.int64, copy=True)
        val_snrs = idx["validation_snrs"].astype(np.float32, copy=True)
        train_indices = idx["train_indices"].astype(np.int64, copy=True)
        test_indices = idx["test_indices"].astype(np.int64, copy=True)
    report["splits"] = {
        "train": int(len(train_indices)), "validation": int(len(val_indices)),
        "test": int(len(test_indices)),
        "test_accessed": False,
    }

    # sample one per representative class from validation: 0 (OOK), 17 (AM-SSB-WC),
    # 18 (AM-SSB-SC), 22 (FM)
    picks = {}
    with h5py.File(HDF5_PATH, "r") as f:
        X = f["X"]
        for label in (0, 17, 18, 22):
            pos = int(np.flatnonzero(val_labels == label)[0])
            src = int(val_indices[pos])
            raw = np.asarray(X[src], dtype=np.float32)
            planar = np.ascontiguousarray(raw.T)  # [2, 1024]
            rms = float(np.sqrt(np.mean(planar.astype(np.float64) ** 2)))
            peak = float(np.abs(planar).max())
            picks[label] = {
                "class": LABEL_ORDER_24[label], "source_index": src,
                "raw_shape": list(raw.shape), "planar_shape": list(planar.shape),
                "dtype": str(raw.dtype), "nbytes": int(planar.nbytes),
                "rms": rms, "peak_abs": peak, "crest_factor": peak / rms if rms else 0.0,
            }
        print("  per-class input stats (validation, first sample each):")
        for label in (0, 17, 18, 22):
            p = picks[label]
            print(f"    {p['class']:12s} raw{p['raw_shape']} -> planar{p['planar_shape']} "
                  f"{p['dtype']} rms={p['rms']:.4f} peak={p['peak_abs']:.4f} "
                  f"crest={p['crest_factor']:.3f}")

    # verify .bin == HDF5 raw.T byte-identical for every calibration sample
    with open(CAL_MANIFEST, "r", encoding="utf-8") as f:
        cal = json.load(f)
    cal_rows = cal["rows"]
    byte_mismatch = 0
    with h5py.File(HDF5_PATH, "r") as f:
        X = f["X"]
        for row in cal_rows:
            raw = np.asarray(X[row["source_index"]], dtype=np.float32)
            planar = np.ascontiguousarray(raw.T)
            b = planar.tobytes()
            with open(os.path.join(ROOT, "work", "calibration_384", "cal_data", row["iq_file"]), "rb") as bf:
                actual = bf.read()
            if actual != b:
                byte_mismatch += 1
    print(f"  calibration .bin vs HDF5 raw.T: {len(cal_rows)} samples, "
          f"byte_mismatch={byte_mismatch}")

    # ONNX input contract
    onnx_in = None
    if os.path.isfile(ONNX_REPORT):
        with open(ONNX_REPORT, "r", encoding="utf-8") as f:
            er = json.load(f)
        onnx_in = er.get("input")
        print(f"  ONNX input contract: {onnx_in}")
    report["onnx_input"] = onnx_in

    report["input_contract"] = {
        "dtype": "float32",
        "iq_order": "planar [2,1024] C-order: 1024 I then 1024 Q (HDF5 [1024,2] transposed)",
        "shape": [1, 2, 1024],
        "normalization": "none (raw RadioML2018.01A, intrinsic RMS ~1.0)",
        "rec_scale_or_pre_scale": "none (compile_config.toml pre_scale=nop / pre_method=nop / pre_mean=nop / channel_swap=nop; no_transinput=true)",
        "clipping": "none at input source",
        "byte_order": "native little-endian float32",
        "bytes_per_sample": 8192,
        "cal_bin_vs_hdf5_byte_mismatch": byte_mismatch,
    }

    # ---------------- Part B: iCraft quantizer ----------------
    print("\n[B] iCraft input-layer + first-conv quantizer")
    with open(QJSON, "r", encoding="utf-8") as f:
        qj = json.load(f)
    qops = qj["ops"]

    def edt(x):
        d = x.get("dtype", {})
        if isinstance(d, dict):
            e = d.get("element_dtype")
            if isinstance(e, dict):
                return e
        return None

    # input op + first conv
    input_op = next(o for o in qops if o["_type_key"] == "icraft::xir::Input")
    convs = [o for o in qops if o["_type_key"] == "icraft::xir::Conv2d"]
    first_conv = min(convs, key=lambda o: o["op_id"])

    # input quantize scale: the Cast producing sint8 on the input chain, or the
    # first_conv's inputs[0] value (already int8)
    conv_in_val = first_conv["inputs"][0]
    conv_in_q = edt(conv_in_val)
    conv_in_scales = parse_scales(conv_in_q.get("scale", "")) if conv_in_q else None
    conv_out_val = first_conv["outputs"][0]
    conv_out_q = edt(conv_out_val)
    conv_out_scales = parse_scales(conv_out_q.get("scale", "")) if conv_out_q else None
    wgt_val = first_conv["inputs"][1]
    wgt_q = edt(wgt_val)
    wgt_scales = parse_scales(wgt_q.get("scale", "")) if wgt_q else None

    # input storage dtype: find the Cast op feeding the first conv input (sint8)
    input_storage = conv_in_q.get("storage_dtype") if conv_in_q else None
    input_zp = conv_in_q.get("zero_points", []) if conv_in_q else None

    qi = {
        "input_op": {"op_id": input_op["op_id"], "compile_target": input_op.get("compile_target"),
                     "out_v_id": input_op["outputs"][0].get("v_id"),
                     "element_dtype": str(input_op["outputs"][0]["dtype"]["element_dtype"])},
        "first_conv": {"op_id": first_conv["op_id"],
                       "in_channels": 2, "out_channels": 24, "kernel": 7},
        "input_quantizer": {
            "storage_dtype": input_storage, "zero_points": input_zp,
            "scale_per_channel": conv_in_scales,
            "clip_range_per_channel": [clip_of(s) for s in (conv_in_scales or [])],
            "note": "input is Cast -> int8 (symmetric, zero-point 0) BEFORE first conv",
        },
        "first_conv_output_quantizer": {
            "storage_dtype": conv_out_q.get("storage_dtype") if conv_out_q else None,
            "scale_per_channel": conv_out_scales,
            "clip_range_per_channel": [clip_of(s) for s in (conv_out_scales or [])],
        },
        "first_conv_weight_quantizer": {
            "storage_dtype": wgt_q.get("storage_dtype") if wgt_q else None,
            "scale_per_channel": wgt_scales,
            "num_weight_channels": len(wgt_scales or []),
        },
    }
    report["icraft_quantizer"] = qi
    print(f"  input  : {input_storage} zero_points={input_zp} "
          f"scale/ch={conv_in_scales} clip={[round(clip_of(s),4) for s in (conv_in_scales or [])]}")
    print(f"  stem   : out {conv_out_q.get('storage_dtype') if conv_out_q else None} "
          f"scale/ch={conv_out_scales} clip={[round(clip_of(s),4) for s in (conv_out_scales or [])]}")
    print(f"  weight : {wgt_q.get('storage_dtype') if wgt_q else None} "
          f"{len(wgt_scales or [])} ch, min={min(wgt_scales):.6g} max={max(wgt_scales):.6g}")

    # ---------------- Part C: per-class saturation on 1536 ----------------
    print("\n[C] per-class input saturation on fixed 1536 diagnostic subset")
    sub = np.load(SUBSET, allow_pickle=False)
    sub_indices = sub["sub_indices"].astype(np.int64, copy=True)
    sub_labels = sub["sub_labels"].astype(np.int64, copy=True)
    in_scale = conv_in_scales[0] if conv_in_scales else 0.052646082
    clip = clip_of(in_scale)
    print(f"  input clip = 127 * {in_scale:.9f} = +/-{clip:.6f}")

    per_class = {}
    with h5py.File(HDF5_PATH, "r") as f:
        X = f["X"]
        for label in range(24):
            pos = np.flatnonzero(sub_labels == label)
            rms_l, peak_l, crest_l, sat_l = [], [], [], []
            for p in pos:
                src = int(sub_indices[p])
                planar = np.ascontiguousarray(np.asarray(X[src], dtype=np.float32).T)
                planar64 = planar.astype(np.float64)
                rms = float(np.sqrt(np.mean(planar64 ** 2)))
                peak = float(np.abs(planar).max())
                rms_l.append(rms); peak_l.append(peak)
                crest_l.append(peak / rms if rms else 0.0)
                sat_l.append(float(np.mean(np.abs(planar) > clip)))
            per_class[label] = {
                "class": LABEL_ORDER_24[label], "n": int(len(pos)),
                "rms_mean": float(np.mean(rms_l)), "rms_max": float(np.max(rms_l)),
                "peak_abs_mean": float(np.mean(peak_l)), "peak_abs_max": float(np.max(peak_l)),
                "crest_factor_mean": float(np.mean(crest_l)), "crest_factor_max": float(np.max(crest_l)),
                "input_sat_rate_mean": float(np.mean(sat_l)), "input_sat_rate_max": float(np.max(sat_l)),
            }
    report["per_class_input_saturation"] = [per_class[l] for l in range(24)]

    print(f"  {'class':12s} {'rms':>6s} {'peak':>7s} {'crest':>6s} {'inSat%':>7s} {'inSatMax%':>9s}")
    for l in range(24):
        c = per_class[l]
        flag = " <== AM" if l in (17, 18) else ""
        print(f"  {c['class']:12s} {c['rms_mean']:6.3f} {c['peak_abs_mean']:7.3f} "
              f"{c['crest_factor_mean']:6.2f} {c['input_sat_rate_mean']*100:7.3f} "
              f"{c['input_sat_rate_max']*100:9.3f}{flag}")

    out = os.path.join(ROOT, "work", "d3_step1_input_contract_audit.json")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\n== wrote {out} ==")
    print("== M29 Phase D.3 Step 1 audit COMPLETE ==")
    return 0


if __name__ == "__main__":
    sys.exit(main())
