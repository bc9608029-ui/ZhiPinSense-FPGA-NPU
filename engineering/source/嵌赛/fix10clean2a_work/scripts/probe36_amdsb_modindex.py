"""Measure real AM-DSB modulation index and envelope stats; compare to candidate."""
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


def sawtooth(rng, phase=None):
    if phase is None:
        phase = rng.uniform(0, 1)
    n = np.arange(N)
    return 2.0 * ((n / N + phase) % 1.0) - 1.0


def measure_env(env_c):
    """env_c: complex envelope (demodulated, low-passed). Report carrier + audio stats."""
    dc = env_c.mean(axis=1, keepdims=True)
    audio = env_c - dc
    carrier = np.abs(dc).mean()
    audio_rms = np.sqrt(np.mean(np.abs(audio) ** 2))
    env_amp = np.abs(env_c)
    env_papr = 10 * np.log10((env_amp ** 2).max() / (env_amp ** 2).mean())
    return carrier, audio_rms, env_papr


def main():
    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        X = f["X"]
        tt = np.arange(N) / FS
        for name in ["AM-DSB-WC", "AM-DSB-SC"]:
            q = np.where((Z == 30) & (Y[:, ORDER.index(name)] == 1))[0][:400]
            xr = (X[q][:, :, 0] + 1j * X[q][:, :, 1]).astype(np.complex128)
            b = xr * np.exp(-1j * 2 * np.pi * FC * tt)[None, :]
            B = np.fft.fft(b, axis=1)
            fbin = np.fft.fftfreq(N, 1 / FS)
            mask = np.abs(fbin) <= 3000.0
            B[:, ~mask] = 0.0
            env_c = np.fft.ifft(B, axis=1)
            carrier, audio_rms, env_papr = measure_env(env_c)
            print(f"{name}: carrier={carrier:.4f} audio_rms={audio_rms:.4f} "
                  f"mod_index(audio/carrier)={audio_rms/carrier:.4f} env_PAPR={env_papr:.2f}dB")

    # candidate reference: complex envelope, two independent sawtooths, unit RMS audio
    print("\ncandidate (complex envelope, 2 indep sawtooth, s_c rms=sqrt(2/3)=0.8165):")
    for A, m in [(1.0, 0.05), (1.0, 0.07), (1.0, 0.10), (1.0, 0.15), (1.0, 0.20), (1.0, 0.3), (1.0, 0.4)]:
        rng = np.random.default_rng(0)
        fr = []
        for _ in range(400):
            sI = sawtooth(rng)
            sQ = sawtooth(rng)
            env_c = A + m * (sI + 1j * sQ)
            fr.append(env_c)
        fr = np.array(fr)
        carrier, audio_rms, env_papr = measure_env(fr)
        print(f"  A={A:.2f} m={m:.2f}: carrier={carrier:.4f} audio_rms={audio_rms:.4f} "
              f"mod_index={audio_rms/carrier:.4f} env_PAPR={env_papr:.2f}dB")


if __name__ == "__main__":
    main()
