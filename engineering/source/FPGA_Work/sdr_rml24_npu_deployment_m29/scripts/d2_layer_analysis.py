#!/usr/bin/env python
"""M29 Phase D.2 — per-layer FP32 vs INT8(SFB) activation deviation analysis.

Reads the frozen 1536-sample diagnostic subset (validation, NOT test), runs the
fp32 checkpoint (forward hooks) and the ExpA INT8 model (icraft-run
--dump_ftmp --dump_format SFB) on each sample, and computes per-layer
cosine / SQNR / MAE / dynamic-range / saturation, split by AM-SSB-SC /
AM-SSB-WC / other classes, to locate the first layer of significant deviation.

READ-ONLY: no test access, no board, no model changes, no calibration change.

Usage:
  python d2_layer_analysis.py --json <ZG.json> --raw <ZG.raw> \
      --work-dir <dir> --out-dir <dir> [--verify N]
  (--verify N : process only the first N samples for a smoke test)
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import subprocess
import sys
import time

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import numpy as np  # noqa: E402
import torch  # noqa: E402

ROOT = r"F:\FPGA_Work\sdr_rml24_npu_deployment_m29"
V11 = r"F:\FPGA_Work\sdr_amr_rml24_ood_v1_1"
CHECKPOINT = r"F:\FPGA_Work\24class_results\rml24_seed2027_best.pt"
HDF5_PATH = r"F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5"
CHECKPOINT_SHA = "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d"
SUBSET = os.path.join(ROOT, "work", "eval_full", "subset_index.npz")
ICRAFT_RUN = r"D:\icraft\bin\icraft-run.exe"

AM_SSB_WC, AM_SSB_SC = 17, 18

# (boundary_name, int8 v_id, fp32 hook name, logical_shape, is_bf16_in_expA)
BOUNDARIES = [
    ("input",              0,    "input",                    (2, 1024),   False),
    ("den.stem_out",       510,  "denoiser.stem.2",          (24, 1024),  False),
    ("den.b0.conv2",       514,  "denoiser.blocks.0.bn2",    (24, 1024),  False),
    ("den.b0.out",         45,   "denoiser.blocks.0",        (24, 1024),  False),
    ("den.b1.conv2",       518,  "denoiser.blocks.1.bn2",    (24, 1024),  False),
    ("den.b1.out",         76,   "denoiser.blocks.1",        (24, 1024),  False),
    ("den.b2.conv2",       522,  "denoiser.blocks.2.bn2",    (24, 1024),  False),
    ("den.b2.out",         107,  "denoiser.blocks.2",        (24, 1024),  False),
    ("den.correction",     526,  "denoiser.correction",      (2, 1024),   False),
    ("denoised",           121,  "denoiser",                 (2, 1024),   False),
    ("feat0.proj",         530,  "features.0.projection.1",  (32, 512),   False),
    ("feat0.conv2",        534,  "features.0.bn2",           (32, 512),   False),
    ("feat0.out",          164,  "features.0",               (32, 512),   False),
    ("feat1.conv2",        538,  "features.1.bn2",           (32, 512),   False),
    ("feat1.out",          195,  "features.1",               (32, 512),   False),
    ("feat2.proj",         542,  "features.2.projection.1",  (48, 256),   False),
    ("feat2.conv2",        546,  "features.2.bn2",           (48, 256),   False),
    ("feat2.out",          238,  "features.2",               (48, 256),   False),
    ("feat3.conv2",        550,  "features.3.bn2",           (48, 256),   False),
    ("feat3.out",          269,  "features.3",               (48, 256),   False),
    ("feat4.proj",         554,  "features.4.projection.1",  (64, 128),   False),
    ("feat4.conv2",        558,  "features.4.bn2",           (64, 128),   False),
    ("feat4.out",          312,  "features.4",               (64, 128),   False),
    ("feat5.conv2",        562,  "features.5.bn2",           (64, 128),   False),
    ("feat5.out",          343,  "features.5",               (64, 128),   False),
    ("feat6.proj",         566,  "features.6.projection.1",  (96, 64),    False),
    ("feat6.conv2",        570,  "features.6.bn2",           (96, 64),    False),
    ("feat6.out",          386,  "features.6",               (96, 64),    False),
    ("feat7.conv2",        574,  "features.7.bn2",           (96, 64),    False),
    ("feat7.out",          417,  "features.7",               (96, 64),    False),
    ("mean",               419,  "classifier.input",         (96,),       False),
    ("fc1",                425,  "classifier.1",             (128,),      False),
    ("fc2_logits",         429,  "classifier.3",             (24,),       True),
]

GROUPS = [("all", None), ("am_ssb_sc", AM_SSB_SC), ("am_ssb_wc", AM_SSB_WC), ("other", "other")]

DUMP_IDS = ",".join(str(b[1]) for b in BOUNDARIES if b[1] != 0)


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_scales(s: str) -> list[float]:
    """Parse '@scales([axis=..]24*0.05,8*1)' -> flat list of floats."""
    inner = s.strip()
    if inner.startswith("@scales("):
        inner = inner[len("@scales("):-1]
    if inner.startswith("["):
        close = inner.index("]")
        inner = inner[close + 1:]
    out: list[float] = []
    for term in inner.split(","):
        term = term.strip()
        if not term:
            continue
        if "*" in term:
            cnt, val = term.split("*", 1)
            out.extend([float(val)] * int(cnt))
        else:
            out.append(float(term))
    return out


def build_scale_map(json_path: str) -> dict[int, list[float]]:
    """v_id -> scale list (flat, in storage order) for every int8 output tensor."""
    d = json.load(open(json_path, encoding="utf-8"))
    m: dict[int, list[float]] = {}
    for op in d["ops"]:
        for out in op.get("outputs", []):
            dt = out.get("dtype", {}).get("element_dtype")
            if isinstance(dt, dict) and dt.get("_type_key") == "icraft::xir::QuantizedType":
                sc = dt.get("scale")
                if isinstance(sc, str):
                    m[int(out["v_id"])] = parse_scales(sc)
    return m


def _channel_scales(scales: list[float], shape: tuple) -> np.ndarray:
    """Return per-channel scale vector for a canonical [C,L] (or [N]) tensor."""
    if len(shape) == 1:
        n = shape[0]
        if len(scales) >= n:
            return np.asarray(scales[:n], dtype=np.float64)
        return np.full(n, scales[0], dtype=np.float64)
    c = shape[0]
    if len(scales) >= c:
        return np.asarray(scales[:c], dtype=np.float64)
    return np.full(c, scales[0], dtype=np.float64)


def saturation(int8_vals: np.ndarray, shape: tuple, scales: np.ndarray) -> float:
    v = int8_vals.reshape(shape).astype(np.float64)
    if len(shape) == 2:
        q = v / scales[:, None]
    else:
        q = v / scales
    q = np.round(q)
    return float(((q >= 127.0) | (q <= -127.0)).mean())


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    a = a.reshape(-1).astype(np.float64)
    b = b.reshape(-1).astype(np.float64)
    na = float(np.linalg.norm(a)); nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def metrics(fp: np.ndarray, it: np.ndarray, shape: tuple, scales: np.ndarray | None):
    f = fp.reshape(shape).astype(np.float64)
    i = it.reshape(shape).astype(np.float64)
    f = f.reshape(-1); i = i.reshape(-1)
    err = f - i
    ssq_f = float(np.dot(f, f)); ssq_e = float(np.dot(err, err))
    sqnr = 10.0 * np.log10(ssq_f / ssq_e) if ssq_e > 0 else float("inf")
    cos = cosine(f, i)
    mae = float(np.abs(err).mean())
    rms_f = float(np.sqrt(ssq_f / f.size))
    sat = saturation(it, shape, scales) if scales is not None else None
    return {
        "cos": cos, "sqnr": sqnr, "mae": mae, "mae_norm": float(mae / rms_f) if rms_f > 0 else 0.0,
        "rms_fp32": rms_f, "fp32_min": float(f.min()), "fp32_max": float(f.max()),
        "int8_min": float(i.min()), "int8_max": float(i.max()), "sat": sat,
    }


def main() -> int:
    if not os.path.exists(ARGS.json) or not os.path.exists(ARGS.raw):
        print("FAIL: model json/raw missing"); return 1
    if sha256_file(CHECKPOINT) != CHECKPOINT_SHA:
        print("FAIL: checkpoint sha"); return 1

    scale_map = build_scale_map(ARGS.json)
    print(f"scale map: {len(scale_map)} int8 tensors")

    # build fp32 model + hooks
    sys.path.insert(0, V11)
    from models.rml24_net import build_rml24_model
    ckpt = torch.load(CHECKPOINT, map_location="cpu", weights_only=True)
    cfg = {"denoiser_channels": 24, "denoiser_blocks": 3, "feature_channels": [32, 48, 64, 96],
           "classifier_hidden": 128, "dropout": 0.15}
    model = build_rml24_model(24, **cfg)
    model.load_state_dict(ckpt["model_state"], strict=True)
    model.eval()

    import torch.nn as nn
    caps: dict[str, np.ndarray] = {}
    handles = []

    def hook_for(name):
        def hook(mod, inp, out):
            if isinstance(out, torch.Tensor):
                caps[name] = out.detach().cpu().numpy().copy()
            elif isinstance(out, (tuple, list)) and isinstance(out[0], torch.Tensor):
                caps[name] = out[0].detach().cpu().numpy().copy()
        return hook

    for name, mod in model.named_modules():
        if isinstance(mod, (nn.Conv1d, nn.BatchNorm1d, nn.ReLU, nn.Linear)):
            handles.append(mod.register_forward_hook(hook_for(name)))
        if mod.__class__.__name__ in ("ResidualUnit", "DeployableResidualDenoiser"):
            handles.append(mod.register_forward_hook(hook_for(name)))
    handles.append(model.classifier[0].register_forward_pre_hook(
        lambda mod, inp: caps.__setitem__("classifier.input", inp[0].detach().cpu().numpy().copy())))

    with np.load(SUBSET, allow_pickle=False) as z:
        sub_indices = z["sub_indices"].astype(np.int64)
        sub_labels = z["sub_labels"].astype(np.int64)
    n_total = len(sub_indices)
    n = int(ARGS.verify) if ARGS.verify else n_total
    print(f"subset = {n_total} samples; processing first {n}")

    os.makedirs(ARGS.work_dir, exist_ok=True)
    ftmp_dir = os.path.join(ARGS.work_dir, ".icraft", "logs", "model_24class", "ftmpSFB")

    # accumulators: boundary x group -> {sum fields, count}
    accum = {}
    for (bname, _, _, shape, _) in BOUNDARIES:
        for gname, _ in GROUPS:
            accum[(bname, gname)] = {
                "n": 0, "cos_sum": 0.0, "sqnr_sum": 0.0, "mae_sum": 0.0, "mae_norm_sum": 0.0,
                "ssq_f": 0.0, "ssq_e": 0.0, "sat_sum": 0.0, "sat_n": 0,
                "fp32_min": float("inf"), "fp32_max": float("-inf"),
                "int8_min": float("inf"), "int8_max": float("-inf"),
            }

    import h5py
    t0 = time.time()
    with h5py.File(HDF5_PATH, "r") as f:
        X = f["X"]
        for i in range(n):
            src = int(sub_indices[i])
            lbl = int(sub_labels[i])
            raw = np.asarray(X[src], dtype=np.float32)          # [1024,2]
            planar = np.ascontiguousarray(raw.T)                # [2,1024]
            in_bin = os.path.join(ARGS.work_dir, f"iq_{i}.bin")
            planar.tofile(in_bin)

            # fp32 forward
            x = torch.from_numpy(planar[None, :, :])
            with torch.inference_mode():
                model(x)
            fp_input = planar

            # int8 forward (SFB dump)
            for old in glob.glob(os.path.join(ftmp_dir, "*.ftmp")):
                os.remove(old)
            cmd = [ICRAFT_RUN, "--json", ARGS.json, "--raw", ARGS.raw, "--network", "model_24class",
                   "--input", in_bin, "--backends", "Host", "--dump_ftmp", DUMP_IDS, "--dump_format", "SFB"]
            subprocess.run(cmd, cwd=ARGS.work_dir, stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=True, timeout=180)

            gname = "am_ssb_sc" if lbl == AM_SSB_SC else ("am_ssb_wc" if lbl == AM_SSB_WC else "other")
            for (bname, vid, hook, shape, is_bf16) in BOUNDARIES:
                if vid == 0:
                    it = fp_input
                else:
                    p = os.path.join(ftmp_dir, f"{vid}.ftmp")
                    if not os.path.exists(p):
                        raise RuntimeError(f"missing {vid}.ftmp for sample {i}")
                    it = np.fromfile(p, dtype=np.float32)
                fp = caps[hook] if hook != "input" else fp_input
                scales = None if (is_bf16 or vid == 0) else _channel_scales(scale_map.get(vid, [1.0]), shape)
                if scales is not None and len(scales) == 0:
                    scales = None
                m = metrics(fp, it, shape, scales)
                fp_flat = np.asarray(fp, dtype=np.float64).reshape(-1)
                it_flat = np.asarray(it, dtype=np.float64).reshape(-1)
                err_flat = fp_flat - it_flat
                for gkey in ("all", gname):
                    a = accum[(bname, gkey)]
                    a["n"] += 1
                    a["cos_sum"] += m["cos"]; a["sqnr_sum"] += m["sqnr"]
                    a["mae_sum"] += m["mae"]; a["mae_norm_sum"] += m["mae_norm"]
                    a["ssq_f"] += float(np.dot(fp_flat, fp_flat))
                    a["ssq_e"] += float(np.dot(err_flat, err_flat))
                    if m["sat"] is not None:
                        a["sat_sum"] += m["sat"] * fp_flat.size; a["sat_n"] += fp_flat.size
                    a["fp32_min"] = min(a["fp32_min"], m["fp32_min"]); a["fp32_max"] = max(a["fp32_max"], m["fp32_max"])
                    a["int8_min"] = min(a["int8_min"], m["int8_min"]); a["int8_max"] = max(a["int8_max"], m["int8_max"])

            for old in glob.glob(os.path.join(ftmp_dir, "*.ftmp")):
                os.remove(old)
            if (i + 1) % 16 == 0 or (i + 1) == n:
                rate = (i + 1) / (time.time() - t0)
                eta = (n - i - 1) / rate if rate > 0 else 0.0
                print(f"  [{i+1}/{n}] rate={rate:.2f} samp/s ETA={eta/60:.1f} min")

    # finalize
    report = {"phase": "M29-Phase-D.2-layer-localization", "subset_size": n,
              "json_sha": sha256_file(ARGS.json), "raw_sha": sha256_file(ARGS.raw),
              "boundaries": []}
    for (bname, vid, hook, shape, is_bf16) in BOUNDARIES:
        entry = {"boundary": bname, "v_id": vid, "shape": list(shape), "bf16": is_bf16, "groups": {}}
        for gname, _ in GROUPS:
            a = accum[(bname, gname)]
            if a["n"] == 0:
                continue
            n = a["n"]
            pooled_sqnr = 10.0 * np.log10(a["ssq_f"] / a["ssq_e"]) if a["ssq_e"] > 0 else float("inf")
            entry["groups"][gname] = {
                "n": n,
                "cos_mean": a["cos_sum"] / n,
                "sqnr_mean_db": a["sqnr_sum"] / n,
                "sqnr_pooled_db": pooled_sqnr,
                "mae_mean": a["mae_sum"] / n,
                "mae_norm_mean": a["mae_norm_sum"] / n,
                "fp32_range": [a["fp32_min"], a["fp32_max"]],
                "int8_range": [a["int8_min"], a["int8_max"]],
                "sat_rate": (a["sat_sum"] / a["sat_n"]) if a["sat_n"] else None,
            }
        report["boundaries"].append(entry)

    os.makedirs(ARGS.out_dir, exist_ok=True)
    out = os.path.join(ARGS.out_dir, "d2_layer_analysis_report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2)
    print(f"\n== wrote {out} ==")

    # print compact table
    print("\nboundary                 group        cos     SQNRdB   MAE     sat")
    for b in report["boundaries"]:
        g = b["groups"].get("all")
        if g:
            sat = f"{g['sat_rate']:.4f}" if g["sat_rate"] is not None else "N/A"
            print(f"{b['boundary']:24s} all       {g['cos_mean']:.4f}  {g['sqnr_mean_db']:7.2f} {g['mae_mean']:.5f} {sat}")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", required=True)
    ap.add_argument("--raw", required=True)
    ap.add_argument("--work-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--verify", type=int, default=0)
    ARGS = ap.parse_args()
    sys.exit(main())
