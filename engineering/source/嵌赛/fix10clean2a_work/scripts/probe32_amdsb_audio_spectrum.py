"""Average demodulated AM-DSB audio spectrum + envelope stats over many frames."""
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
            q = np.where((Z == 30) & (Y[:, ORDER.index(name)] == 1))[0][:400]
            xr = (X[q][:, :, 0] + 1j * X[q][:, :, 1]).astype(np.complex128)
            a = xr * np.exp(-1j * 2 * np.pi * FC * tt)[None, :]
            # remove DC (carrier), get audio
            audio = a - a.mean(axis=1, keepdims=True)
            # average magnitude spectrum of audio (positive freqs)
            A = np.mean(np.abs(np.fft.fft(audio, axis=1)[:, :N // 2]), axis=0)
            fpos = np.fft.fftfreq(N, 1 / FS)[:N // 2]
            A = A / A.max()
            # print bins 1..40 (195..7812 Hz) magnitude
            print(f"\n=== {name} audio spectrum (mag, excl DC), bins 1..20 ===")
            for i in range(1, 21):
                bar = "#" * int(A[i] * 50)
                print(f"  {fpos[i]:6.0f} Hz: {A[i]:.3f} {bar}")
            # audio real vs imag power
            print(f"  audio.real rms={audio.real.std():.3f}  audio.imag rms={audio.imag.std():.3f}")
            # envelope of original
            env = np.abs(xr)
            print(f"  orig env min={env.min():.4f} PAPR={10*np.log10((env**2).max()/(env**2).mean()):.2f}dB")


if __name__ == "__main__":
    main()
