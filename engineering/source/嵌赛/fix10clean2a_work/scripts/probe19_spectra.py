"""Dump average magnitude spectra + I/Q structure for the 5 broken classes.

Shows (a) whether the signal is real (Q~0) or complex, (b) spectral peak
locations (DC vs carrier), (c) spectral bandwidth.  Prints compact summaries.
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
ORDER = c.LABEL_ORDER_24
BROKEN = ["OQPSK", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC"]
FS = c.SAMPLE_RATE_HZ


def spectrum_stats(x):
    I = x.real
    Q = x.imag
    q_ratio = float(np.mean(Q ** 2) / (np.mean(I ** 2) + 1e-12))
    X = np.fft.fftshift(np.fft.fft(x))
    freqs = np.fft.fftshift(np.fft.fftfreq(len(x), 1 / FS))
    P = np.abs(X) ** 2
    P = P / P.max()
    # peak location
    pk = float(freqs[np.argmax(P)])
    # fractional power in |f| < 1kHz (DC band)
    dc = float(np.sum(P[np.abs(freqs) < 1000]) / np.sum(P))
    return {"q_i_ratio": round(q_ratio, 3), "peak_hz": round(pk, 1),
            "dc_frac_lt1k": round(dc, 3)}


def main():
    report = {}
    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        X = f["X"]
        for name in BROKEN:
            cidx = ORDER.index(name)
            q = np.where((Z == 30) & (Y[:, cidx] == 1))[0][:300]
            xr = (X[q][:, :, 0] + 1j * X[q][:, :, 1]).astype(np.complex128)
            sr = np.mean([np.array(list(spectrum_stats(x).values())) for x in xr], axis=0)
            keys = list(spectrum_stats(xr[0]).keys())
            rstat = dict(zip(keys, sr))
            xg = np.stack([c.generate_class(name, 6000 + i) for i in range(300)])
            sg = np.mean([np.array(list(spectrum_stats(x).values())) for x in xg], axis=0)
            gstat = dict(zip(keys, sg))
            report[name] = {"real": rstat, "clean": gstat}
            print(f"\n=== {name} ===")
            for k in keys:
                print(f"  {k:<14} real={rstat[k]:>10}  clean={gstat[k]:>10}")

    Path(r"F:/嵌赛/fix10clean2a_results/PROBE19_SPECTRA.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print("\n-> PROBE19_SPECTRA.json")


if __name__ == "__main__":
    main()
