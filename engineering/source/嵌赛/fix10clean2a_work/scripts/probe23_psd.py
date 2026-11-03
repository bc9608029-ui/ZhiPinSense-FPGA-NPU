"""Compare average PSD (|H(f)|^2) of real OQPSK/AM-DSB vs candidate generators.

The PSD of a white-symbol pulse-shaped signal is the pulse's |H(f)|^2, so this
identifies the exact pulse/band for OQPSK and AM-DSB.
"""
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
N = c.SAMPLE_LENGTH


def psd(x_frames):
    P = np.zeros(N // 2)
    for x in x_frames:
        X = np.fft.fft(x)
        P += np.abs(X[:N // 2]) ** 2
    P /= P.sum()
    return P


def bands(P):
    f = np.fft.rfftfreq(N, 1 / FS)[:N // 2]
    out = []
    for lo, hi in [(0, 500), (500, 1500), (1500, 3000), (3000, 4500), (4500, 6250), (6250, 9000), (9000, 13000)]:
        m = (f >= lo) & (f < hi)
        out.append(round(float(P[m].sum()), 3))
    return out


def main():
    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        X = f["X"]
        # real OQPSK
        q = np.where((Z == 30) & (Y[:, ORDER.index("OQPSK")] == 1))[0][:400]
        xr = (X[q][:, :, 0] + 1j * X[q][:, :, 1]).astype(np.complex128)
        Pr = psd(xr)
        print("band edges(Hz): 0-500, 500-1500, 1500-3000, 3000-4500, 4500-6250, 6250-9000, 9000-13000")
        print(f"real OQPSK PSD    : {bands(Pr)}")

        # my wsinc OQPSK
        def my_oqpsk(rng):
            bits = 2.0 * rng.integers(0, 2, size=2 * c.N_SYMBOLS) - 1.0
            i = bits[0::2]; q = bits[1::2]
            xi = c._pulse_shape(i, c.SPS, c._H)
            xq = c._pulse_shape(q, c.SPS, c._H)
            d = c.SPS // 2
            xqd = np.zeros_like(xq); xqd[d:] = xq[:-d]
            return xi + 1j * xqd
        Pm = psd([my_oqpsk(np.random.default_rng(i)) for i in range(400)])
        print(f"my wsinc OQPSK PSD: {bands(Pm)}")

        # real AM-DSB-WC / SC
        for name in ["AM-DSB-WC", "AM-DSB-SC"]:
            q = np.where((Z == 30) & (Y[:, ORDER.index(name)] == 1))[0][:400]
            xr = (X[q][:, :, 0] + 1j * X[q][:, :, 1]).astype(np.complex128)
            Pr = psd(xr)
            print(f"real {name} PSD  : {bands(Pr)}")


if __name__ == "__main__":
    main()
