#!/usr/bin/env python3
"""stage_c_preprocess_ablation.py -- 12 legal, global, category-agnostic,
deployable preprocessing ablations.  Same FP32 ONNX, same label order, no weight
changes, no per-frame best-transform selection, no majority voting, no logit
hacking, no test-frame hyperparameter selection reported as generalization.

For each transform we report (on the SAME 78 real frames, transformed uniformly):
    QPSK top-1 count/ratio, QPSK avg softmax prob, confusion histogram,
    mean max-prob confidence, logits L1 delta vs baseline,
    and the SAME transform's effect on RadioML QPSK (golden accuracy guard),
    plus compute cost class and board-deployability.

Output: out/preprocess_ablation.json + console table.
"""
from __future__ import annotations

import glob
import json
import os
import time
from collections import Counter

import numpy as np
import h5py
import onnxruntime as ort

HDF5 = r"F:/datasets/RadioML2018/GOLD_XYZ_OSC.0001_1024.hdf5"
IDX = r"F:/FPGA_Work/sdr_amr_rml24_ood_v1_1/data/radioml2018/rml24_split_indices.npz"
ONNX = r"F:/FPGA_Work/sdr_rml24_npu_deployment_m29/work/onnx/rml24_24class_opset17.onnx"
REAL = r"C:/Users/shado/Downloads/rml23_analysis_20261011_225430/rml23_capture_39e5_final_1773383076"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

LABEL_ORDER_24 = ("OOK","4ASK","8ASK","BPSK","QPSK","8PSK","16PSK","32PSK",
    "16APSK","32APSK","64APSK","128APSK","16QAM","32QAM","64QAM",
    "128QAM","256QAM","AM-SSB-WC","AM-SSB-SC","AM-DSB-WC",
    "AM-DSB-SC","FM","GMSK","OQPSK")

FS = 128000.0
N = 1024
T = np.arange(N) / FS


def cfo_hz_4th(x):
    Y = np.fft.fft(x ** 4)
    f = np.fft.fftfreq(N, 1.0 / FS)
    return float(f[int(np.argmax(np.abs(Y)))] / 4.0)


def to_iq(x):
    return np.stack([x.real, x.imag]).astype(np.float32)


# ---- 12 legal transforms: iq [2,1024] float32 -> iq' [2,1024] float32 ----

def t_baseline(iq):
    return np.ascontiguousarray(iq, dtype=np.float32)          # no-op

def t_dc_removal(iq):
    x = iq[0] + 1j * iq[1]
    x = x - x.mean()
    return to_iq(x)

def t_rms_norm(iq):
    x = iq[0] + 1j * iq[1]
    x = x / np.sqrt(np.mean(np.abs(x) ** 2))
    return to_iq(x)

def t_dc_rms(iq):
    x = iq[0] + 1j * iq[1]
    x = x - x.mean()
    x = x / np.sqrt(np.mean(np.abs(x) ** 2))
    return to_iq(x)

def t_fixed_cfo(iq):
    x = iq[0] + 1j * iq[1]
    x = x * np.exp(1j * 2 * np.pi * 250.0 * T)   # correct known -250 Hz offset
    return to_iq(x)

def t_estimated_cfo(iq):
    x = iq[0] + 1j * iq[1]
    cfo = cfo_hz_4th(x)                          # blind, label-agnostic estimate
    x = x * np.exp(-1j * 2 * np.pi * cfo * T)
    return to_iq(x)

def t_phase_rotation(iq):
    x = iq[0] + 1j * iq[1]
    x = x * np.exp(1j * np.pi / 4)               # fixed global 45 deg
    return to_iq(x)

def t_iq_swap(iq):
    return np.ascontiguousarray(iq[::-1], dtype=np.float32)

def t_q_negation(iq):
    out = iq.copy(); out[1] = -out[1]
    return np.ascontiguousarray(out, dtype=np.float32)

def t_window_shift(iq):
    return np.ascontiguousarray(np.roll(iq, 128, axis=1), dtype=np.float32)

def t_bw_align(iq):
    """Fixed FFT-domain low-pass to RadioML -20 dB occupied bandwidth edge
    (~8.125 kHz one-sided), trimming only the real signal's outer skirt."""
    x = iq[0] + 1j * iq[1]
    X = np.fft.fft(x)
    freq = np.fft.fftfreq(N, 1.0 / FS)
    cutoff = 8125.0
    # raised-cosine transition to keep the filter legal/clean
    W = np.ones(N)
    for i, f in enumerate(freq):
        a = np.abs(f)
        if a > cutoff + 2000.0:
            W[i] = 0.0
        elif a > cutoff - 2000.0:
            W[i] = 0.5 * (1 + np.cos(np.pi * (a - (cutoff - 2000.0)) / 4000.0))
    return to_iq(np.fft.ifft(X * W))

def t_exact_loader(iq):
    # training loader __getitem__ does: ascontiguousarray(raw.T) with NO norm.
    # real frames are already [I,Q] planar = raw.T form -> identity in content.
    return np.ascontiguousarray(iq, dtype=np.float32)


TRANSFORMS = [
    ("1_no_processing_baseline",       t_baseline,       "O(N)",   "memcpy (already identity)"),
    ("2_per_frame_complex_dc_removal", t_dc_removal,     "O(N)",   "per-frame mean subtract (deployable)"),
    ("3_rms_norm_to_radioml",          t_rms_norm,       "O(N)",   "per-frame unit-RMS scale (deployable)"),
    ("4_dc_plus_rms",                  t_dc_rms,         "O(N)",   "DC remove + RMS scale (deployable)"),
    ("5_fixed_cfo_plus250",            t_fixed_cfo,      "O(N)",   "complex NCO mix (deployable)"),
    ("6_estimated_cfo_4th",            t_estimated_cfo,  "O(N log N)", "FFT-based blind CFO (deployable)"),
    ("7_global_phase_rotation_45",     t_phase_rotation, "O(N)",   "fixed phase rotate (deployable)"),
    ("8_iq_swap",                      t_iq_swap,        "O(N)",   "I/Q swap (deployable)"),
    ("9_q_negation_conjugate",         t_q_negation,     "O(N)",   "conjugate (deployable)"),
    ("10_window_circular_shift_128",   t_window_shift,   "O(N)",   "circular shift (deployable)"),
    ("11_bw_align_lowpass",            t_bw_align,       "O(N log N)", "FFT low-pass to RadioML -20dB edge (deployable)"),
    ("12_exact_training_loader",       t_exact_loader,   "O(N)",   "identity (already in loader form)"),
]


def load_real():
    frames = []
    for p in sorted(glob.glob(os.path.join(REAL, "live_rx_tensor_*.f32"))):
        d = np.fromfile(p, dtype="<f4").reshape(2, 1024)
        frames.append(d.astype(np.float32))
    return frames


def load_radioml_qpsk(n=200, snr=30.0):
    z = np.load(IDX, allow_pickle=False)
    ti, tl, ts = z["test_indices"], z["test_labels"], z["test_snrs"]
    mask = (tl == 4) & (np.abs(ts - snr) < 1e-6)
    sel = np.where(mask)[0][:n]
    h5 = h5py.File(HDF5, "r"); X = h5["X"]
    out = [np.ascontiguousarray(np.asarray(X[int(ti[k])]).T.astype(np.float32)) for k in sel]
    h5.close()
    return out


def softmax(l):
    e = np.exp(l - l.max()); return e / e.sum()


def main():
    os.makedirs(OUT, exist_ok=True)
    sess = ort.InferenceSession(ONNX, providers=["CPUExecutionProvider"])
    iname = sess.get_inputs()[0].name

    def infer(iq_list):
        out = []
        for iq in iq_list:
            out.append(sess.run(None, {iname: iq[None]})[0][0])
        return np.array(out)

    real = load_real()
    rm = load_radioml_qpsk(n=200)

    base_logits = infer(real)
    base_top1 = [int(np.argmax(l)) for l in base_logits]

    rows = []
    for name, fn, cost, deploy in TRANSFORMS:
        t0 = time.perf_counter()
        real_t = [fn(iq) for iq in real]
        rm_t = [fn(iq) for iq in rm]
        t1 = time.perf_counter()

        real_l = infer(real_t)
        rm_l = infer(rm_t)

        real_top1 = [int(np.argmax(l)) for l in real_l]
        rm_top1 = [int(np.argmax(l)) for l in rm_l]
        real_hist = Counter(LABEL_ORDER_24[i] for i in real_top1)
        rm_hist = Counter(LABEL_ORDER_24[i] for i in rm_top1)

        qpsk_idx = 4
        qpsk_cnt = sum(1 for i in real_top1 if i == qpsk_idx)
        qpsk_prob = float(np.mean([softmax(l)[qpsk_idx] for l in real_l]))
        conf = float(np.mean([softmax(l).max() for l in real_l]))
        # logits L1 delta vs baseline (same 24-dim space)
        l1 = float(np.mean([np.abs(real_l[k] - base_logits[k]).sum() for k in range(len(real))]))
        rm_golden = rm_hist.get("QPSK", 0)

        rows.append({
            "transform": name,
            "compute_cost": cost,
            "board_deployable": deploy,
            "qpsk_top1_count": qpsk_cnt,
            "qpsk_top1_ratio": round(qpsk_cnt / len(real), 4),
            "qpsk_avg_prob": round(qpsk_prob, 6),
            "mean_max_confidence": round(conf, 6),
            "logits_l1_delta_vs_baseline": round(l1, 6),
            "radioml_golden_qpsk_count": rm_golden,
            "radioml_golden_qpsk_ratio": round(rm_golden / len(rm), 4),
            "real_confusion_histogram": dict(sorted(real_hist.items())),
            "real_top1_qpsk_vs_qam": {"QPSK": qpsk_cnt, "QAM": len(real) - qpsk_cnt},
            "transform_us_per_frame": round((t1 - t0) / len(real) * 1e6, 2),
        })

    with open(os.path.join(OUT, "preprocess_ablation.json"), "w", encoding="utf-8") as f:
        json.dump({"n_real_frames": len(real), "n_radioml_frames": len(rm),
                   "baseline_top1": dict(sorted(Counter(LABEL_ORDER_24[i] for i in base_top1).items())),
                   "label_order_24": list(LABEL_ORDER_24),
                   "rows": rows}, f, indent=2)

    print("=== Stage C preprocessing ablation (78 real QPSK, same FP32 ONNX) ===")
    print("%-34s %6s %10s %10s %7s %8s" % ("transform", "QPSK", "ratio", "avgP", "L1d", "RMgold"))
    for r in rows:
        print("%-34s %6d %10.4f %10.6f %7.2f  %d/%d" % (
            r["transform"], r["qpsk_top1_count"], r["qpsk_top1_ratio"],
            r["qpsk_avg_prob"], r["logits_l1_delta_vs_baseline"],
            r["radioml_golden_qpsk_count"], len(rm)))
    print()
    print("baseline real top-1:", dict(sorted(Counter(LABEL_ORDER_24[i] for i in base_top1).items())))
    print("wrote", os.path.join(OUT, "preprocess_ablation.json"))


if __name__ == "__main__":
    main()
