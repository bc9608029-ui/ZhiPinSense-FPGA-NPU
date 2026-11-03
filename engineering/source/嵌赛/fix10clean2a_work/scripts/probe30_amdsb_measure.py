"""Measure AM-DSB carrier frequency, audio bandwidth, and WC/SC difference."""
from __future__ import annotations

import os
import sys

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
N = c.SAMPLE_LENGTH


def main():
    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        X = f["X"]
        freqs = np.fft.fftfreq(N, 1 / FS)
        for name in ["AM-DSB-WC", "AM-DSB-SC"]:
            q = np.where((Z == 30) & (Y[:, ORDER.index(name)] == 1))[0][:400]
            xr = (X[q][:, :, 0] + 1j * X[q][:, :, 1]).astype(np.complex128)
            # average |X(f)| over frames, positive freqs only
            P = np.zeros(N // 2)
            for x in xr:
                P += np.abs(np.fft.fft(x)[:N // 2])
            P /= P.max()
            fpos = np.fft.fftfreq(N, 1 / FS)[:N // 2]
            # peak frequency
            pk = fpos[np.argmax(P)]
            # -3dB and -20dB edges
            thr3 = P.max() * 0.707
            thr20 = P.max() * 0.1
            above3 = fpos[P >= thr3]
            above20 = fpos[P >= thr20]
            print(f"\n=== {name} ===")
            print(f"  peak freq = {pk:.0f} Hz")
            print(f"  -3dB band = [{above3.min():.0f}, {above3.max():.0f}] Hz (width {above3.max()-above3.min():.0f})")
            print(f"  -20dB band = [{above20.min():.0f}, {above20.max():.0f}] Hz (width {above20.max()-above20.min():.0f})")
            # envelope stats (audio characteristic)
            env = np.abs(xr)
            print(f"  env min={env.min():.4f} mean={env.mean():.3f} PAPR={10*np.log10((env**2).max()/(env**2).mean()):.2f}dB")
            # spectrum at the 10 strongest bins (to see carrier vs sidebands)
            top = np.argsort(P)[-8:]
            top = sorted(top, key=lambda i: -P[i])
            print("  top bins (freq: rel-pwr):",
                  ", ".join(f"{fpos[i]:.0f}:{P[i]:.2f}" for i in top))


if __name__ == "__main__":
    main()
