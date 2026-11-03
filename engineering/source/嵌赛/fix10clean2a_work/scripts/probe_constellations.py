"""Extract the real RadioML2018.01A constellation levels (I/Q) for QAM/ASK/APSK."""
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
         "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
         "FM", "GMSK", "OQPSK"]


def sinc(x):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.abs(x) < 1e-12, 1.0, np.sin(np.pi * x) / (np.pi * x))


def wsinc(fc, ntaps, window="hann"):
    n = np.arange(ntaps) - (ntaps - 1) / 2.0
    h = 2.0 * fc * sinc(2.0 * fc * n)
    w = np.hanning(ntaps)
    return (h * w) / np.sqrt(np.sum((h * w) ** 2))


def levels(v, nb=60):
    hist, edges = np.histogram(v, bins=nb)
    thresh = hist.max() * 0.03
    centers = (edges[:-1] + edges[1:]) / 2
    peaks = np.sort(centers[hist > thresh])
    merged = []
    scale = max(1.0, np.abs(peaks).max()) if len(peaks) else 1.0
    for p in peaks:
        if merged and abs(p - merged[-1]) < 0.05 * scale:
            merged[-1] = (merged[-1] + p) / 2
        else:
            merged.append(p)
    return np.round(np.array(merged), 3)


def main():
    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        H = wsinc(0.059, 65)
        for cidx in [12, 13, 14, 15, 16, 8, 9, 10, 11, 1, 2, 0]:
            name = ORDER[cidx]
            q = np.where((Z == 30) & (Y[:, cidx] == 1))[0][:300]
            x = (f["X"][q][:, :, 0] + 1j * f["X"][q][:, :, 1]).astype(np.complex128)
            # matched filter + best sampling offset over all frames
            best_std = 1e9
            best_s = None
            for off in range(SPS):
                y = np.convolve(x[0], H)[(len(H) - 1) // 2:(len(H) - 1) // 2 + N]
                s = y[off::SPS]
                s = s / np.sqrt(np.mean(np.abs(s) ** 2))
                if np.std(np.abs(s)) < best_std:
                    best_std = np.std(np.abs(s))
                    best_s = s
            I = np.real(best_s)
            Q = np.imag(best_s)
            if "APSK" in name:
                print(f"{name:<8} |s| levels = {levels(np.abs(best_s), 60)}  (amp std {best_std:.3f})")
            else:
                print(f"{name:<8} I={levels(I)}  Q={levels(Q)}  (amp std {best_std:.3f})")


if __name__ == "__main__":
    main()
