#!/usr/bin/env python3
"""diagnose_smearing.py -- is RadioML's |x|^2 smearing caused by multipath
(frequency-selective fading) or by pulse shaping?  Multipath leaves deep,
irregular notches in a SINGLE frame's linear PSD |FFT(x)|^2; pulse shaping
gives a smooth deterministic PSD.  Compare single-frame PSD ripple vs the
clean real capture.  Read-only, no model, no board.
"""
import glob
import os

import numpy as np
import h5py

HDF5 = r"F:/datasets/RadioML2018/GOLD_XYZ_OSC.0001_1024.hdf5"
IDX = r"F:/FPGA_Work/sdr_amr_rml24_ood_v1_1/data/radioml2018/rml24_split_indices.npz"
REAL = r"C:/Users/shado/Downloads/rml23_analysis_20261011_225430/rml23_capture_39e5_final_1773383076"
FS = 128000.0
N = 1024


def single_psd_metrics(x):
    P = np.abs(np.fft.fft(x)) ** 2
    Ps = np.fft.fftshift(P)
    freq = np.fft.fftshift(np.fft.fftfreq(N, 1.0 / FS))
    pos = freq >= 0
    Ppos, fpos = Ps[pos], freq[pos]
    band = (fpos >= 500) & (fpos <= 15000)   # passband, skip DC
    Pb = Ppos[band]
    # smooth with a moving average to estimate the underlying pulse spectrum
    w = 41
    kernel = np.ones(w) / w
    Psmooth = np.convolve(Pb, kernel, mode="same")
    rel = Pb / (Psmooth + 1e-300)
    ripple_db = 10 * np.log10(np.percentile(rel, 90) / (np.percentile(rel, 10) + 1e-300) + 1e-300)
    deep = int(np.sum(Pb < 0.1 * np.max(Pb)))
    env = np.abs(x)
    return {
        "env_cv": env.std() / env.mean(),
        "psd_ripple_p90p10_db": ripple_db,
        "deep_notch_bins": deep,
    }


print("=== single-frame PSD ripple: multipath vs pulse shaping ===")

with np.load(IDX, allow_pickle=False) as z:
    ti, tl, ts = z["test_indices"], z["test_labels"], z["test_snrs"]
m = (tl == 4) & (np.abs(ts - 30) < 1e-6)
sel = np.where(m)[0][:4]
h5 = h5py.File(HDF5, "r")
X = h5["X"]
print("--- RadioML QPSK @30dB (single frames) ---")
for k in sel:
    raw = np.asarray(X[int(ti[k])], dtype=np.float64)
    x = raw[:, 0] + 1j * raw[:, 1]
    d = single_psd_metrics(x)
    print("  env cv=%.3f  PSD ripple(p90/p10)=%.1f dB  deep notch bins=%d"
          % (d["env_cv"], d["psd_ripple_p90p10_db"], d["deep_notch_bins"]))
h5.close()

print("--- Real capture (single frames) ---")
for p in sorted(glob.glob(os.path.join(REAL, "live_rx_tensor_*.f32")))[:4]:
    raw = np.fromfile(p, dtype="<f4").reshape(2, N).astype(np.float64)
    x = raw[0] + 1j * raw[1]
    d = single_psd_metrics(x)
    print("  env cv=%.3f  PSD ripple(p90/p10)=%.1f dB  deep notch bins=%d"
          % (d["env_cv"], d["psd_ripple_p90p10_db"], d["deep_notch_bins"]))
