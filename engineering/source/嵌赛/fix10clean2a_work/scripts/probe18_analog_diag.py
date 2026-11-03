"""Diagnose the 5 broken classes: compare real (30 dB) vs clean-generated signal
features — RMS, |mean|, PAPR, spectral centre/bandwidth, inst-freq std, and a
coarse envelope histogram — to find the mismatch the model keys on.
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


def features(x: np.ndarray):
    """x: complex 1024 frame."""
    rms = float(np.sqrt(np.mean(np.abs(x) ** 2)))
    mean_abs = float(np.abs(np.mean(x)))
    env = np.abs(x)
    papr = float(10 * np.log10((env.max() ** 2) / (np.mean(env ** 2) + 1e-12)))
    # spectrum
    X = np.fft.fftshift(np.fft.fft(x))
    freqs = np.fft.fftshift(np.fft.fftfreq(len(x), 1 / FS))
    P = np.abs(X) ** 2
    cen = float(np.sum(freqs * P) / (np.sum(P) + 1e-12))
    # inst freq (unwrap phase diff)
    ph = np.unwrap(np.angle(x))
    inst = np.diff(ph) * FS / (2 * np.pi)
    return {"rms": round(rms, 4), "mean_abs": round(mean_abs, 4),
            "papr_db": round(papr, 2), "spec_center_hz": round(cen, 1),
            "inst_freq_std_hz": round(float(np.std(inst)), 1),
            "env_min": round(float(env.min()), 4),
            "env_max": round(float(env.max()), 4)}


def main():
    report = {}
    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        X = f["X"]
        for name in BROKEN:
            cidx = ORDER.index(name)
            q = np.where((Z == 30) & (Y[:, cidx] == 1))[0][:200]
            xr = (X[q][:, :, 0] + 1j * X[q][:, :, 1]).astype(np.complex128)
            # real features averaged over 200 frames
            fr = {}
            for k in features(xr[0]):
                fr[k] = float(np.mean([features(x)[k] for x in xr]))
            # my clean features averaged over 200 frames
            xg = np.stack([c.generate_class(name, 5000 + i) for i in range(200)])
            fg = {}
            for k in features(xg[0]):
                fg[k] = float(np.mean([features(x)[k] for x in xg]))
            report[name] = {"real": fr, "clean": fg}
            print(f"\n=== {name} ===")
            for k in fr:
                print(f"  {k:<18} real={fr[k]:>12}  clean={fg[k]:>12}")

    Path(r"F:/嵌赛/fix10clean2a_results/PROBE18_ANALOG_DIAG.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")
    print("\n-> PROBE18_ANALOG_DIAG.json")


if __name__ == "__main__":
    main()
