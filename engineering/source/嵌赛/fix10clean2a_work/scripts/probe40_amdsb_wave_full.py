"""Dump full-frame AM-DSB audio waveform at coarse resolution + peak freq."""
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
            q = np.where((Z == 30) & (Y[:, ORDER.index(name)] == 1))[0][:1]
            x = (X[q][0, :, 0] + 1j * X[q][0, :, 1]).astype(np.complex128)
            b = x * np.exp(-1j * 2 * np.pi * FC * tt)
            B = np.fft.fft(b)
            fbin = np.fft.fftfreq(N, 1 / FS)
            B[np.abs(fbin) > 3000.0] = 0.0
            env_c = np.fft.ifft(B)
            dc = env_c.mean()
            audio = (env_c - dc) * np.exp(-1j * np.angle(dc))
            a = audio.real
            print(f"\n=== {name} audio waveform, every 16 samples (64 pts over frame) ===")
            print("   " + " ".join(f"{a[16*i]:+.3f}" for i in range(64)))
            print(f"   min={a.min():+.3f} max={a.max():+.3f}")
            # find where the max is, and zero crossings
            zc = np.where(np.diff(np.sign(a)) != 0)[0]
            print(f"   zero-crossings: {len(zc)}  (sawtooth ~1, sine@195Hz ~2)")
            print(f"   argmax at sample {np.argmax(a)}, argmin at sample {np.argmin(a)}")


if __name__ == "__main__":
    main()
