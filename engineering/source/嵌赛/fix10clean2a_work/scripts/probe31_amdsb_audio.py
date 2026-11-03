"""Demodulate AM-DSB carrier (6250 Hz) to recover the exact audio signal a[n]."""
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
        for name in ["AM-DSB-WC", "AM-DSB-SC"]:
            q = np.where((Z == 30) & (Y[:, ORDER.index(name)] == 1))[0][:1]
            x = (X[q][0, :, 0] + 1j * X[q][0, :, 1]).astype(np.complex128)
            tt = np.arange(N) / FS
            # demodulate carrier
            a = x * np.exp(-1j * 2 * np.pi * FC * tt)
            print(f"\n=== {name} (one frame, demodulated audio a[n] = x*exp(-j2pi*6250*t)) ===")
            print("  a[0:16] real:", " ".join(f"{v:+.3f}" for v in a.real[:16]))
            print("  a[0:16] imag:", " ".join(f"{v:+.3f}" for v in a.imag[:16]))
            print(f"  a.real mean={a.real.mean():+.4f}  a.imag mean={a.imag.mean():+.4f}")
            print(f"  |a| min={np.abs(a).min():.4f} max={np.abs(a).max():.4f} mean={np.abs(a).mean():.4f}")
            # spectrum of the demodulated audio
            A = np.abs(np.fft.fft(a)[:N // 2])
            fpos = np.fft.fftfreq(N, 1 / FS)[:N // 2]
            top = np.argsort(A)[-6:][::-1]
            print("  audio spectrum top bins:", ", ".join(f"{fpos[i]:.0f}Hz:{A[i]/A.max():.2f}" for i in top))


if __name__ == "__main__":
    main()
