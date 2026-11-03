"""Extract APSK ring radii by DIRECT sampling at Gardner timing (no matched filter).

Matched-filtering needs the exact pulse PHASE; direct sampling avoids that —
at the symbol instant, x[n] ~ s_i * h[d], so |x[n]| ~ |s_i| * |h[d]| and the
ring RATIOS are preserved even with some ISI smear.

Also confirms the APSK data-part pulse == wsinc via g[k].
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
SPS = 8
N = 1024
ORDER = ["OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
         "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
         "128QAM", "256QAM"]


def sinc(x):
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.abs(x) < 1e-12, 1.0, np.sin(np.pi * x) / (np.pi * x))


def wsinc(fc=0.059, ntaps=65):
    n = np.arange(ntaps) - (ntaps - 1) / 2.0
    h = 2.0 * fc * sinc(2.0 * fc * n)
    h = h * np.hanning(ntaps)
    return h / np.sqrt(np.sum(h ** 2))


def gardner_offset(x):
    m = np.abs(x) ** 2
    nn = np.arange(N)
    C = np.sum(m * np.exp(-2j * np.pi * nn / SPS), axis=1)
    C = np.sum(C)
    return int(round(-np.angle(C) * SPS / (2 * np.pi))) % SPS


def rings_from_radii(r, nbins=120, thresh_frac=0.015, merge_frac=0.02):
    hist, edges = np.histogram(r, bins=nbins)
    centers = (edges[:-1] + edges[1:]) / 2
    peaks = np.sort(centers[hist > hist.max() * thresh_frac])
    scale = peaks.max() if len(peaks) else 1.0
    merged = []
    for p in peaks:
        if merged and abs(p - merged[-1]) < merge_frac * scale:
            merged[-1] = (merged[-1] + p) / 2
        else:
            merged.append(p)
    return np.array(merged)


def main():
    report = {}
    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        # confirm APSK data-part pulse == wsinc
        print("=== APSK g[k] (data-part autocorr) vs wsinc ===")
        H = wsinc()
        # wsinc reference g[k]
        def pulse_autocorr(h, kmax=12):
            R = np.correlate(h, h, "full")
            R = R[R.size // 2:]
            return R[:kmax] / R[0]
        g_wsinc = pulse_autocorr(H)
        print(f"wsinc g[1..11] = {np.round(g_wsinc[1:12], 4)}")

        for cidx in [9, 10, 11]:
            q = np.where((Z == 30) & (Y[:, cidx] == 1))[0][:300]
            x = (f["X"][q][:, :, 0] + 1j * f["X"][q][:, :, 1]).astype(np.complex128)
            # g[k] via autocorr
            M = len(x)
            R = np.zeros(12)
            for k in range(12):
                R[k] = np.real(np.sum(x[:, :N - k] * np.conj(x[:, k:])) / M / (N - k))
            R /= R[0]
            print(f"{ORDER[cidx]:<6} g[1..11] = {np.round(R[1:12], 4)}")

            # direct-sample at Gardner timing -> ring radii
            off = gardner_offset(x)
            s = x[:, off::SPS].ravel()
            r = np.abs(s)
            radii = rings_from_radii(r)
            radii = radii / radii[0] if len(radii) else radii
            print(f"          direct-sample |s| ratios = {np.round(radii, 3)}  (off={off})")
            report[ORDER[cidx]] = {"offset": off, "ratios": np.round(radii, 3).tolist()}

    Path(r"F:/嵌赛/fix10clean2a_results/PROBE4_APSK_RINGS.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print("\n-> PROBE4_APSK_RINGS.json")


if __name__ == "__main__":
    main()
