"""Print representative I/Q time samples + spectrum bands for the analog classes
to reveal the exact generation structure (real vs complex, carrier location)."""
from __future__ import annotations

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
ORDER = c.LABEL_ORDER_24
FS = c.SAMPLE_RATE_HZ


def bands(x):
    X = np.fft.fft(x)
    f = np.fft.fftfreq(len(x), 1 / FS)
    out = {}
    for lo, hi in [(0, 100), (100, 1000), (1000, 3000), (3000, 6250), (6250, 9000), (9000, 15000)]:
        m = (np.abs(f) >= lo) & (np.abs(f) < hi)
        out[f"{lo}-{hi}"] = round(float(np.sum(np.abs(X[m]) ** 2) / np.sum(np.abs(X) ** 2)), 3)
    return out


def main():
    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        X = f["X"]
        for name in ["AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC"]:
            cidx = ORDER.index(name)
            q = np.where((Z == 30) & (Y[:, cidx] == 1))[0][:200]
            xr = (X[q][:, :, 0] + 1j * X[q][:, :, 1]).astype(np.complex128)
            I = xr.real.mean(axis=0)
            Q = xr.imag.mean(axis=0)
            # variance of I and Q across frames at each sample (to see if it's
            # real (Q~0) or complex)
            Iv = X[q][:, :, 0].std(axis=0)
            Qv = X[q][:, :, 1].std(axis=0)
            print(f"\n=== {name} ===")
            print(f"  I[0:8] mean   = {np.round(I[:8], 2)}")
            print(f"  Q[0:8] mean   = {np.round(Q[:8], 2)}")
            print(f"  I std(mean)   = {np.round(Iv.mean(), 3)}  Q std = {np.round(Qv.mean(), 3)}")
            print(f"  I mean-of-all = {np.round(I.mean(), 3)}  Q mean = {np.round(Q.mean(), 3)}")
            print(f"  spectrum bands (frac power): {bands(xr[0])}")
            # envelope stats
            env = np.abs(xr[0])
            print(f"  |x|: min={env.min():.3f} max={env.max():.3f} mean={env.mean():.3f}")


if __name__ == "__main__":
    main()
