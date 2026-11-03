#!/usr/bin/env python3
"""per_frame_env_spec.py -- is RadioML QPSK "smeared" per-frame, or only when
averaged?  Check single-frame |x|^2 symbol-line position + prominence vs the
300-frame average.  Read-only, no model, no board.
"""
import numpy as np
import h5py

HDF5 = r"F:/datasets/RadioML2018/GOLD_XYZ_OSC.0001_1024.hdf5"
IDX = r"F:/FPGA_Work/sdr_amr_rml24_ood_v1_1/data/radioml2018/rml24_split_indices.npz"
FS = 128000.0
N = 1024
BIN = FS / N

with np.load(IDX, allow_pickle=False) as z:
    ti, tl, ts = z["test_indices"], z["test_labels"], z["test_snrs"]
m = (tl == 4) & (np.abs(ts - 30) < 1e-6)          # QPSK @ 30 dB
sel = np.where(m)[0][:8]
h5 = h5py.File(HDF5, "r")
X = h5["X"]
frames = []
for k in sel:
    raw = np.asarray(X[int(ti[k])], dtype=np.float64)
    frames.append(raw[:, 0] + 1j * raw[:, 1])
h5.close()


def env_spec(x):
    e = np.abs(x) ** 2
    e = e - e.mean()
    return np.abs(np.fft.fft(e))


def summarize(S, label):
    half = N // 2
    seg = S[1:half]
    order = np.argsort(seg)[::-1]
    pk = (order[0] + 1) * BIN
    pk2 = (order[1] + 1) * BIN
    prom = seg[order[0]] / seg[order[1]]
    print("%-28s peak=%8.1f Hz  second=%8.1f Hz  prominence(top/2nd)=%.3f"
          % (label, pk, pk2, prom))
    return pk


print("=== per-frame |x|^2 symbol line (RadioML QPSK @30dB) ===")
peaks = []
for i, x in enumerate(frames):
    peaks.append(summarize(env_spec(x), "frame %d" % i))

Smean = np.mean([env_spec(x) for x in frames], axis=0)
summarize(Smean, "averaged %d frames" % len(frames))

peaks = np.array(peaks)
print("\nsingle-frame peak positions (Hz):", [round(p) for p in peaks])
print("peak position spread       : %.1f Hz  (min %.0f .. max %.0f)"
      % (peaks.max() - peaks.min(), peaks.min(), peaks.max()))
