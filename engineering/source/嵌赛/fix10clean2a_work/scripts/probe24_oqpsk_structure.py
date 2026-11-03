"""Extract real OQPSK's I/Q timing/phase structure: pulse autocorrelation,
I-Q cross-correlation (offset), and phase-transition histogram."""
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
SPS = c.SPS
N = c.SAMPLE_LENGTH


def main():
    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        X = f["X"]
        q = np.where((Z == 30) & (Y[:, ORDER.index("OQPSK")] == 1))[0][:600]
        xr = (X[q][:, :, 0] + 1j * X[q][:, :, 1]).astype(np.complex128)

        I = xr.real
        Q = xr.imag

        # 1. autocorrelation of I (pulse autocorrelation), averaged over frames
        # (I is real PAM; autocorr ~ pulse autocorr * white symbol variance)
        ac = np.zeros(2 * SPS + 1)
        for row in I:
            ac += np.correlate(row, row, mode="full")[N - 1 - SPS:N - 1 + SPS + 1]
        ac /= np.abs(ac[SPS])
        print("I autocorr (lag -8..+8 samples, normalized):")
        print("  " + " ".join(f"{v:+.2f}" for v in ac[::2]))

        # 2. cross-correlation I * Q shifted (find the offset)
        xc = np.zeros(2 * SPS + 1)
        for i in range(len(I)):
            xc += np.correlate(I[i], Q[i], mode="full")[N - 1 - SPS:N - 1 + SPS + 1]
        xc /= np.max(np.abs(xc))
        print("\nI*Q cross-corr (lag -8..+8):")
        print("  " + " ".join(f"{v:+.2f}" for v in xc))
        print(f"  argmax lag = {np.argmax(np.abs(xc)) - SPS} samples")

        # 3. instantaneous frequency std (confirm)
        ph = np.angle(xr)
        dph = np.diff(np.unwrap(ph, axis=1), axis=1)
        inst = dph / (2 * np.pi / c.SAMPLE_RATE_HZ)
        print(f"\ninst_freq std = {np.std(inst):.0f} Hz, max|inst| = {np.max(np.abs(inst)):.0f} Hz")

        # 4. phase transition histogram at symbol boundaries (every SPS samples)
        # sample the phase at t = k*SPS + SPS//2 (center of each symbol)
        sym_ph = ph[:, SPS // 2::SPS]  # 128 symbols per frame
        d_sym = np.diff(np.unwrap(sym_ph, axis=1), axis=1)  # phase jump per symbol
        d_sym = (d_sym + np.pi) % (2 * np.pi) - np.pi
        hist, edges = np.histogram(d_sym.ravel(), bins=36, range=(-np.pi, np.pi))
        cents = (edges[:-1] + edges[1:]) / 2
        big = [f"{d:.0f}deg:{h}" for d, h in zip(np.degrees(cents), hist) if h > 500]
        print("\nphase-transition histogram (deg:count, peaks):")
        print("  " + ", ".join(big))

        # 5. env stats for reference
        env = np.abs(xr)
        print(f"\nenv_min={env.min():.3f} PAPR(dB)={10*np.log10((env**2).max()/(env**2).mean()):.2f}")


if __name__ == "__main__":
    main()
