"""Match the real OQPSK I-autocorrelation against candidate pulse shapes."""
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


def acorr(h, maxlag):
    h = h / np.sqrt(np.sum(h ** 2))
    out = []
    for t in range(0, maxlag + 1):
        out.append(np.sum(h[t:] * h[:len(h) - t]))
    return np.array(out)


def rrc_taps(alpha, span=8, sps=SPS):
    nsym = span
    k = np.arange(-nsym * sps / 2, nsym * sps / 2 + 1) / sps
    h = np.zeros_like(k)
    for i, t in enumerate(k):
        if abs(t) < 1e-9:
            h[i] = 1 - alpha + 4 * alpha / np.pi
        elif abs(abs(t) - 1 / (4 * alpha)) < 1e-9:
            h[i] = (alpha / np.sqrt(2)) * ((1 + 2 / np.pi) * np.sin(np.pi / (4 * alpha))
                                          + (1 - 2 / np.pi) * np.cos(np.pi / (4 * alpha)))
        else:
            h[i] = (np.sin(np.pi * t * (1 - alpha)) + 4 * alpha * t * np.cos(np.pi * t * (1 + alpha))) \
                   / (np.pi * t * (1 - (4 * alpha * t) ** 2))
    return h / np.sqrt(np.sum(h ** 2))


def rc_taps(alpha, span=8, sps=SPS):
    nsym = span
    k = np.arange(-nsym * sps / 2, nsym * sps / 2 + 1) / sps
    h = np.zeros_like(k)
    for i, t in enumerate(k):
        if abs(abs(t) - 1 / (2 * alpha)) < 1e-9:
            h[i] = np.sinc(1 / (2 * alpha)) * np.pi / 4
        else:
            h[i] = np.sinc(t) * np.cos(np.pi * alpha * t) / (1 - (2 * alpha * t) ** 2)
    return h / np.sqrt(np.sum(h ** 2))


def gauss_taps(bt, span=8, sps=SPS):
    # Gaussian filter for a given BT product
    nsym = span
    k = np.arange(-nsym * sps / 2, nsym * sps / 2 + 1) / sps
    h = np.exp(-2 * np.pi ** 2 * bt ** 2 / np.log(2) * k ** 2)
    return h / np.sqrt(np.sum(h ** 2))


def main():
    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        X = f["X"]
        q = np.where((Z == 30) & (Y[:, ORDER.index("OQPSK")] == 1))[0][:600]
        xr = (X[q][:, :, 0] + 1j * X[q][:, :, 1]).astype(np.complex128)
        I = xr.real
        ac = np.zeros(33)
        for row in I:
            ac += np.correlate(row, row, mode="full")[N - 1:N + 32]
        ac /= np.abs(ac[0])
        real_ac = ac[:17]  # lags 0..16

    cands = {
        "wsinc(fc=0.059)": c.wsinc_taps(),
        "rc a=0.35": rc_taps(0.35),
        "rc a=0.5": rc_taps(0.5),
        "rc a=1.0": rc_taps(1.0),
        "rrc a=0.35": rrc_taps(0.35),
        "rrc a=0.5": rrc_taps(0.5),
        "gauss BT=0.3": gauss_taps(0.3),
        "gauss BT=0.5": gauss_taps(0.5),
    }
    print("real I-autocorr (lags 0,2,4,6,8,10,12,14,16):")
    print("  " + " ".join(f"{v:+.2f}" for v in real_ac[::2]))
    print()
    for name, h in cands.items():
        a = acorr(h, 16)
        a /= a[0]
        print(f"{name:<18} " + " ".join(f"{v:+.2f}" for v in a[::2]))


if __name__ == "__main__":
    main()
