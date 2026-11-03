"""Dump raw I/Q waveform of real OQPSK + wide-range correlation to find the
exact pulse and I-Q offset."""
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

        # raw waveform of one frame (first 32 samples)
        print("raw I[0:32] of one frame:")
        print("  " + " ".join(f"{v:+.2f}" for v in I[0][:32]))
        print("raw Q[0:32]:")
        print("  " + " ".join(f"{v:+.2f}" for v in Q[0][:32]))

        # I autocorrelation over wide range (lags -32..+32)
        ac = np.zeros(65)
        for row in I:
            ac += np.correlate(row, row, mode="full")[N - 1 - 32:N - 1 + 33]
        ac /= np.abs(ac[32])
        print("\nI autocorr (lag -16..+16, step 2):")
        print("  " + " ".join(f"{v:+.2f}" for v in ac[16:49:2]))

        # I-Q cross-correlation over wide range
        xc = np.zeros(65)
        for i in range(len(I)):
            xc += np.correlate(I[i], Q[i], mode="full")[N - 1 - 32:N - 1 + 33]
        xc /= np.max(np.abs(xc))
        print("\nI*Q cross-corr (lag -16..+16, step 2):")
        print("  " + " ".join(f"{v:+.2f}" for v in xc[16:49:2]))
        print(f"  argmax lag = {np.argmax(np.abs(xc)) - 32}")

        # constellation scatter: sample at every SPS with a few phase offsets
        print("\nconstellation (sample at n=0,8,16,... with offset 0):")
        pts = xr[0, ::SPS]
        print("  " + " ".join(f"{p:.2f}" for p in pts[:16]))

        # magnitude of the signal (envelope) first 40 samples
        print("\n|I| (rect pulse => step function) first 32:")
        print("  " + " ".join(f"{abs(v):.2f}" for v in I[0][:32]))


if __name__ == "__main__":
    main()
