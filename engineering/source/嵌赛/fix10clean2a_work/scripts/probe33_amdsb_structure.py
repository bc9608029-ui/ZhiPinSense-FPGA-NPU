"""Decisive AM-DSB structure probe: analytic vs DSB, sideband sign, I/Q correlation."""
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
FC = 6250.0


def main():
    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        X = f["X"]
        tt = np.arange(N) / FS
        for name in ["AM-DSB-WC", "AM-DSB-SC"]:
            q = np.where((Z == 30) & (Y[:, ORDER.index(name)] == 1))[0][:20]
            xr = (X[q][:, :, 0] + 1j * X[q][:, :, 1]).astype(np.complex128)

            # 1) two-sided spectrum (averaged |X(f)|, fftshifted)
            P = np.zeros(N)
            for x in xr:
                P += np.abs(np.fft.fftshift(np.fft.fft(x)))
            P /= P.max()
            fshift = np.fft.fftshift(np.fft.fftfreq(N, 1 / FS))
            pos = P[N // 2:]      # 0..+Nyquist
            neg = P[:N // 2]      # -Nyquist..0
            fpos = fshift[N // 2:]
            print(f"\n=== {name} ===")
            print(f"  energy +freq = {pos.sum():.3f}   -freq = {neg.sum():.3f}  (analytic if -freq ~= 0)")
            # top bins around carrier
            b6250 = int(round(FC / FS * N))
            lo, hi = b6250 - 12, b6250 + 12
            print(f"  |X| near carrier (bin {b6250}=6250Hz), bins {lo}..{hi}:")
            for i in range(lo, hi + 1):
                f = i * FS / N
                bar = "#" * int(pos[i] * 60)
                print(f"    {f:6.0f} Hz: {pos[i]:.3f} {bar}")

            # 2) demodulate, I/Q correlation within a frame
            a = xr * np.exp(-1j * 2 * np.pi * FC * tt)[None, :]
            a0 = a - a.mean(axis=1, keepdims=True)
            # correlation between real & imag (per frame, then mean of |corr|)
            re = a0.real
            im = a0.imag
            corr = []
            for k in range(len(a0)):
                ck = np.corrcoef(re[k], im[k])[0, 1]
                corr.append(ck)
            corr = np.array(corr)
            print(f"  corr(real,imag) per frame: mean={corr.mean():+.3f}  std={corr.std():.3f}")
            print(f"    (|corr|~1 => real-up-to-phase DSB; ~0 => genuinely complex/analytic)")

            # 3) is demodulated audio analytic? (energy at +freq vs -freq of a0)
            Aa = np.zeros(N)
            for ak in a0:
                Aa += np.abs(np.fft.fftshift(np.fft.fft(ak)))
            Aa /= Aa.max()
            apos = Aa[N // 2:].sum()
            aneg = Aa[:N // 2].sum()
            print(f"  audio(no DC) energy +freq={apos:.3f}  -freq={aneg:.3f}  (audio analytic?)")


if __name__ == "__main__":
    main()
