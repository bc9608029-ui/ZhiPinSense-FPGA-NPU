"""Precise AM-DSB audio waveform: full spectrum (bins 1..30) + one-frame time series."""
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
            q = np.where((Z == 30) & (Y[:, ORDER.index(name)] == 1))[0][:100]
            xr = (X[q][:, :, 0] + 1j * X[q][:, :, 1]).astype(np.complex128)
            b = xr * np.exp(-1j * 2 * np.pi * FC * tt)[None, :]
            B = np.fft.fft(b, axis=1)
            fbin = np.fft.fftfreq(N, 1 / FS)
            B[:, np.abs(fbin) > 3000.0] = 0.0
            env_c = np.fft.ifft(B, axis=1)
            dc = env_c.mean(axis=1, keepdims=True)
            audio = env_c - dc

            # averaged magnitude spectrum of audio, bins 1..30 (195..5859 Hz)
            A = np.mean(np.abs(np.fft.fft(audio, axis=1)[:, :N // 2]), axis=0)
            A = A / A[1]  # normalize to fundamental (bin 1)
            print(f"\n=== {name} audio |X| bins 1..20 (norm to bin1=195Hz) ===")
            for i in range(1, 21):
                print(f"  bin{i:2d} {i*FS/N:6.0f}Hz: {A[i]:.3f}")
            # fundamental/rms ratio
            fund = A[1]
            rms = np.sqrt(np.mean(np.abs(audio) ** 2))
            # normalize: fundamental amplitude vs rms (both in same units)
            fund_abs = np.mean(np.abs(np.fft.fft(audio, axis=1)[:, 1]), axis=0)
            print(f"  fund_abs={fund_abs:.5f}  rms={rms:.5f}  ratio fund/rms={fund_abs/rms:.3f}")

            # one-frame time series: first 64 samples of audio (phase-aligned, real)
            a1 = audio[0] * np.exp(-1j * np.angle(dc[0]))
            print(f"  {name} audio[0:64] (real, phase-aligned):")
            print("   " + " ".join(f"{v:+.3f}" for v in a1.real[:64]))


if __name__ == "__main__":
    main()
