"""Extract real APSK envelope modes: histogram |x[n]| over ALL samples/frames.

For a multi-ring APSK the envelope distribution has one mode per ring (even
with ISI smear the modes stay visible as local maxima).  Normalise by the
innermost mode and report ratios + mode count.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

USER_SITE = r"C:\Users\shado\AppData\Roaming\Python\Python313\site-packages"
if os.path.isdir(USER_SITE) and USER_SITE not in sys.path:
    sys.path.insert(0, USER_SITE)

import numpy as np  # noqa: E402
import h5py  # noqa: E402

GOLD = r"F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5"
ORDER = ["OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
         "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
         "128QAM", "256QAM"]


def find_modes(values, nbins=200):
    hist, edges = np.histogram(values, bins=nbins)
    centers = (edges[:-1] + edges[1:]) / 2
    # smooth
    k = np.ones(5) / 5.0
    h = np.convolve(hist.astype(float), k, mode="same")
    # local maxima with prominence
    modes = []
    for i in range(2, len(h) - 2):
        if h[i] > h[i - 1] and h[i] > h[i + 1] and h[i] > h.max() * 0.02:
            # simple local peak (also require non-trivial value)
            modes.append((h[i], centers[i]))
    # merge close modes
    modes.sort(key=lambda t: -t[0])
    merged = []
    for _, x in modes:
        if merged and abs(x - merged[-1]) < 0.08 * (max(x, merged[-1]) + 1e-9):
            continue
        merged.append(x)
    merged.sort()
    return np.array(merged)


def main():
    report = {}
    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        for cidx in [8, 9, 10, 11]:
            q = np.where((Z == 30) & (Y[:, cidx] == 1))[0][:400]
            x = (f["X"][q][:, :, 0] + 1j * f["X"][q][:, :, 1]).astype(np.complex128)
            r = np.abs(x).ravel()
            r = r / np.sqrt(np.mean(r ** 2))  # unit RMS
            modes = find_modes(r)
            if len(modes):
                ratios = modes / modes[0]
            else:
                ratios = modes
            print(f"{ORDER[cidx]:<6} envelope modes (|x|) = {np.round(modes, 3)}  ratios={np.round(ratios, 3)}")
            report[ORDER[cidx]] = {"modes": np.round(modes, 3).tolist(),
                                   "ratios": np.round(ratios, 3).tolist()}

    Path(r"F:/嵌赛/fix10clean2a_results/PROBE11_ENVELOPE_MODES.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print("\n-> PROBE11_ENVELOPE_MODES.json")


if __name__ == "__main__":
    main()
