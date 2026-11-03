"""Resolve AM-DSB audio: real (correlated I/Q) vs complex, and sideband sign.

Demodulate the 6250 Hz carrier, low-pass the 2x-carrier beat away, then check
whether the residual audio is real-up-to-phase (real DSB) or genuinely complex.
"""
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

            # demodulate carrier
            b = xr * np.exp(-1j * 2 * np.pi * FC * tt)[None, :]
            # low-pass: keep |f| <= 3000 Hz (drop the -12500 Hz 2x-carrier beat)
            B = np.fft.fft(b, axis=1)
            fbin = np.fft.fftfreq(N, 1 / FS)
            mask = np.abs(fbin) <= 3000.0
            B[:, ~mask] = 0.0
            blo = np.fft.ifft(B, axis=1)

            # DC (carrier) and audio
            dc = blo.mean(axis=1, keepdims=True)
            audio = blo - dc

            # I/Q correlation of the low-passed audio, per frame
            corr = np.array([np.corrcoef(audio[k].real, audio[k].imag)[0, 1] for k in range(len(audio))])
            print(f"\n=== {name} (low-passed demod audio) ===")
            print(f"  corr(real,imag) mean={corr.mean():+.3f} std={corr.std():.3f}  "
                  f"(~±1 real-up-to-phase DSB; ~0 genuinely complex)")

            # +freq vs -freq energy of audio (exclude DC)
            Aa = np.zeros(N)
            for ak in audio:
                Aa += np.abs(np.fft.fft(ak))
            Aa /= Aa.max()
            # bins: 195 Hz = bin 1, -195 = bin N-1
            b1 = 1
            print(f"  audio |X| at +195Hz={Aa[b1]:.3f}   -195Hz={Aa[N - b1]:.3f}")
            print(f"  audio |X| at +391Hz={Aa[2]:.3f}   -391Hz={Aa[N - 2]:.3f}")
            ppos = Aa[1:N // 2].sum()
            pneg = Aa[N // 2:].sum()
            print(f"  audio energy +freq={ppos:.3f}  -freq={pneg:.3f}  (equal => real DSB)")
            # carrier (DC) magnitude and phase
            print(f"  carrier DC |{dc[0].mean():.3f}| phase={np.angle(dc[0].mean())*180/np.pi:+.1f} deg")
            # audio fundamental phase consistency across frames (is sawtooth phase random?)
            fund = np.array([np.fft.fft(audio[k])[b1] for k in range(len(audio))])
            print(f"  fundamental(195Hz) phase across frames: {np.angle(fund)*180/np.pi}")
            # envelope of original (for PAPR reference)
            env = np.abs(xr)
            print(f"  orig |x| min={env.min():.4f}  PAPR={10*np.log10((env**2).max()/(env**2).mean()):.2f}dB")


if __name__ == "__main__":
    main()
