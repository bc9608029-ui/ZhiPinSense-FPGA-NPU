"""Extract the REAL constellation from RadioML2018.01A frames.

Method: matched filter (known wsinc pulse) sampled at symbol timing, then a
zero-forcing equaliser (invert the pulse autocorrelation matrix) to remove the
ISI of the non-Nyquist pulse.  Verify on synthetic first, then extract real
APSK clouds and report per-ring radii via KDE mode finding.
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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import radioml_clean_contract as c  # noqa: E402

GOLD = r"F:\datasets\RadioML2018\GOLD_XYZ_OSC.0001_1024.hdf5"
ORDER = ["OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
         "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
         "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC",
         "AM-DSB-SC", "FM", "GMSK", "OQPSK"]
SPS = 8
H = c.wsinc_taps()          # 65-tap pulse, symmetric, unit energy
L = len(H)                  # 65


def build_R() -> np.ndarray:
    """Autocorrelation matrix R[i,j] = sum_m h[m] h[m-(i-j)*SPS]."""
    # full autocorrelation of h
    ac = np.correlate(H, H, mode="full")       # length 2L-1, ac[L-1+lag]=R(lag)
    N = c.N_SYMBOLS                              # 128
    R = np.zeros((N, N))
    for i in range(N):
        for j in range(N):
            lag = (i - j) * SPS
            idx = L - 1 + lag
            if 0 <= idx < len(ac):
                R[i, j] = ac[idx]
    return R


def zf_symbols(x: np.ndarray, R_inv: np.ndarray) -> np.ndarray:
    """Matched filter + ZF equalisation -> 128 symbols."""
    # matched filter output sampled at k*SPS
    y = np.correlate(x, H, mode="full")          # len = 1024 + 64
    # y[n] = sum_m x[m] h[m-n]; symbol k at n=k*SPS (offset L-1)
    start = L - 1                                 # h[0] aligns so symbol0 at 0
    mf = y[start:start + c.N_SYMBOLS * SPS:SPS]   # 128 values
    return R_inv @ mf


def modes_1d(values: np.ndarray, nbins=400):
    hist, edges = np.histogram(values, bins=nbins, range=(values.min(), values.max()))
    centers = (edges[:-1] + edges[1:]) / 2
    k = np.ones(9) / 9.0
    h = np.convolve(hist.astype(float), k, mode="same")
    pk = []
    for i in range(2, len(h) - 2):
        if h[i] > h[i - 1] and h[i] > h[i + 1] and h[i] > h.max() * 0.03:
            pk.append(centers[i])
    pk = np.array(sorted(pk))
    return pk


def main():
    R = build_R()
    R_inv = np.linalg.inv(R)

    # ---- verify on synthetic 128APSK (known symbols) ----
    rings = [(4, 1.0), (12, 2.0), (20, 3.0), (28, 4.0), (36, 5.0), (28, 6.0)]
    pts = []
    for count, radius in rings:
        for kk in range(count):
            pts.append(radius * np.exp(1j * 2 * np.pi * kk / count))
    const = np.array(pts)
    rng = np.random.default_rng(0)
    sym = const[rng.integers(0, len(const), size=c.N_SYMBOLS)]
    x = c._pulse_shape(sym, SPS, H)
    srec = zf_symbols(x, R_inv)
    # match recovered to nearest constellation point
    err = np.abs(srec[:, None] - const[None, :]).argmin(axis=1)
    frac_ok = (err == (sym == const[:, None]).argmax(axis=0)).mean() if False else None
    # simpler error metric: distance to nearest const point
    d = np.abs(srec[:, None] - const[None, :]).min(axis=1)
    print(f"synthetic 128APSK: recovered |s| std = {np.std(np.abs(srec)):.3f}, "
          f"min-dist med = {np.median(d):.4f}, max = {np.max(d):.4f}")

    # ---- extract real APSK ----
    report = {}
    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        X = f["X"]
        for cidx in [8, 9, 10, 11]:     # 16/32/64/128 APSK
            q = np.where((Z == 30) & (Y[:, cidx] == 1))[0][:200]
            xx = X[q]
            all_r = []
            for xi in xx:
                xsig = xi[:, 0] + 1j * xi[:, 1]
                s = zf_symbols(xsig, R_inv)
                all_r.append(np.abs(s))
            r = np.concatenate(all_r)
            r = r / np.sqrt(np.mean(r ** 2))   # unit RMS
            modes = modes_1d(r)
            if len(modes):
                ratios = modes / modes[0]
            else:
                ratios = modes
            print(f"{ORDER[cidx]:<7} ring radii (unit-RMS) = {np.round(modes,3)}  ratios={np.round(ratios,3)}")
            report[ORDER[cidx]] = {"radii": np.round(modes, 3).tolist(),
                                   "ratios": np.round(ratios, 3).tolist()}

    Path(r"F:/嵌赛/fix10clean2a_results/PROBE15_EXTRACT_CONST.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print("\n-> PROBE15_EXTRACT_CONST.json")


if __name__ == "__main__":
    main()
