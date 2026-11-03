"""Extract real ASK data-part pulse and APSK ring radii (clean, per-frame timing)."""
from __future__ import annotations

import os
import sys

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import numpy as np  # noqa: E402
import h5py  # noqa: E402

GOLD = r"F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5"
SPS = 8
N = 1024
ORDER = ["OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
         "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
         "128QAM", "256QAM"]


def sinc(x):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.abs(x) < 1e-12, 1.0, np.sin(np.pi * x) / (np.pi * x))


def wsinc(fc, ntaps, window="hann"):
    n = np.arange(ntaps) - (ntaps - 1) / 2.0
    h = 2.0 * fc * sinc(2.0 * fc * n)
    w = np.hanning(ntaps)
    return (h * w) / np.sqrt(np.sum((h * w) ** 2))


def main():
    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        # ASK data-part pulse
        print("=== ASK data-part pulse (g[k] = (R[k]-R_inf)/(R[0]-R_inf)) ===")
        for cidx in [0, 1, 2]:
            q = np.where((Z == 30) & (Y[:, cidx] == 1))[0][:400]
            x = (f["X"][q][:, :, 0] + 1j * f["X"][q][:, :, 1]).astype(np.complex128)
            M = len(x)
            R = np.zeros(64)
            for k in range(64):
                R[k] = np.real(np.sum(x[:, :N - k] * np.conj(x[:, k:])) / M / (N - k))
            R /= R[0]
            inf = R[60]
            g = (R - inf) / (1 - inf)
            print(f"{ORDER[cidx]:<5} R_inf={inf:.4f}  g[1..16]={np.round(g[1:17], 3)}")

        # APSK rings: |s| levels across all frames with per-frame optimal offset
        print("\n=== APSK ring radii (matched-filter |s|, per-frame timing) ===")
        H = wsinc(0.059, 65)
        for cidx in [9, 10, 11]:
            q = np.where((Z == 30) & (Y[:, cidx] == 1))[0][:300]
            x = (f["X"][q][:, :, 0] + 1j * f["X"][q][:, :, 1]).astype(np.complex128)
            all_s = []
            for fr in range(len(x)):
                y = np.convolve(x[fr], H)[(len(H) - 1) // 2:(len(H) - 1) // 2 + N]
                best_std = 1e9
                best = None
                for off in range(SPS):
                    s = y[off::SPS]
                    s = s / np.sqrt(np.mean(np.abs(s) ** 2))
                    if np.std(np.abs(s)) < best_std:
                        best_std = np.std(np.abs(s))
                        best = s
                all_s.append(best)
            all_s = np.concatenate(all_s)
            r = np.abs(all_s)
            hist, edges = np.histogram(r, bins=80)
            thresh = hist.max() * 0.02
            centers = (edges[:-1] + edges[1:]) / 2
            peaks = np.sort(centers[hist > thresh])
            merged = []
            for p in peaks:
                if merged and abs(p - merged[-1]) < 0.06:
                    merged[-1] = (merged[-1] + p) / 2
                else:
                    merged.append(p)
            print(f"{ORDER[cidx]:<6} |s| rings = {np.round(np.array(merged), 3)}")


if __name__ == "__main__":
    main()
