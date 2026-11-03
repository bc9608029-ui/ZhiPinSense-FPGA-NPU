"""Compare measured vs clean ASK spectrum: DC line, AC shape, -20dB bandwidth.

Goal: understand why measured 4ASK/8ASK have bw20 = 1 bin while clean has 0.08.
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
N = c.SAMPLE_LENGTH
FS = c.SAMPLE_RATE_HZ


def stats(iq):
    """Replicate check_clean24_domain_match._stats, return extra diagnostics."""
    M = iq.shape[0]
    power = np.abs(iq) ** 2
    mean_pow = power.mean(axis=1)
    win = np.hanning(N)
    psd = np.mean(np.abs(np.fft.fftshift(np.fft.fft(iq * win, axis=1), axes=1)) ** 2, axis=0)
    psd /= psd.sum() + 1e-12
    freqs = np.fft.fftshift(np.fft.fftfreq(N))
    pos = freqs >= 0.0
    pos_psd = psd[pos]
    peak = pos_psd.max()
    peak_freq = freqs[pos][pos_psd.argmax()]
    mask20 = pos_psd >= peak * 1e-2
    bw20 = 2.0 * freqs[pos][mask20][-1] if mask20.any() else 0.0
    # mean of complex signal
    mean_c = np.abs(iq.mean(axis=1)).mean()
    rms = np.sqrt(mean_pow.mean())
    return {
        "mean": mean_c, "rms": rms, "mean_rms_ratio": mean_c / rms,
        "peak": peak, "peak_freq_frac": peak_freq, "bw20": bw20,
        "pos_psd": pos_psd, "freqs_pos": freqs[pos],
    }


def main():
    with h5py.File(GOLD, "r") as f:
        Y = f["Y"][:]
        Z = f["Z"][:, 0]
        X = f["X"]
        for name in ["OOK", "4ASK", "8ASK"]:
            ci = ORDER.index(name)
            q = np.where((Z == 30) & (Y[:, ci] == 1))[0][:200]
            xr = (X[q][:, :, 0] + 1j * X[q][:, :, 1]).astype(np.complex128)
            s = stats(xr)
            print(f"\n=== measured {name} (SNR30, 200 frames) ===")
            print(f"  |mean|={s['mean']:.4f} rms={s['rms']:.4f} ratio={s['mean_rms_ratio']:.4f}")
            print(f"  psd peak={s['peak']:.3e} at f={s['peak_freq_frac']:.4f}  bw20={s['bw20']:.4f}")
            # DC bin value vs AC (bin 10, 20, 30, 40, 50)
            fp = s["freqs_pos"]
            for bi in [0, 1, 2, 3, 5, 10, 20, 30, 40, 50, 60, 80]:
                if bi < len(fp):
                    print(f"    PSD[f={fp[bi]:.4f}] = {s['pos_psd'][bi]:.4e}  ({10*np.log10(s['pos_psd'][bi]/s['peak']):.1f} dB)")

    # clean
    for name in ["OOK", "4ASK", "8ASK"]:
        fr = np.stack([c.generate_class(name, 500000 + i) for i in range(200)])
        s = stats(fr)
        print(f"\n=== clean {name} (200 frames) ===")
        print(f"  |mean|={s['mean']:.4f} rms={s['rms']:.4f} ratio={s['mean_rms_ratio']:.4f}")
        print(f"  psd peak={s['peak']:.3e} at f={s['peak_freq_frac']:.4f}  bw20={s['bw20']:.4f}")
        fp = s["freqs_pos"]
        for bi in [0, 1, 2, 3, 5, 10, 20, 30, 40, 50, 60, 80]:
            if bi < len(fp):
                print(f"    PSD[f={fp[bi]:.4f}] = {s['pos_psd'][bi]:.4e}  ({10*np.log10(s['pos_psd'][bi]/s['peak']):.1f} dB)")


if __name__ == "__main__":
    main()
