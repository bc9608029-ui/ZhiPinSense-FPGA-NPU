#!/usr/bin/env python3
# plot_resampler_response.py -- FIR magnitude response + alias-suppression curve
# for each candidate board sample rate (2.56 MHz x20, 3.84 MHz x30).
#
# Two panels per candidate:
#   left : |H(f)| in dB over [0, fs_in/2], with passband (50 kHz) and stopband
#          (64 kHz = fs_out/2) markers;
#   right: worst-case alias leakage into each output bin f_out in [0, 64 kHz] --
#          max |H(f_out + k*fs_out)| over all input images k that fold onto f_out.
#          This is the anti-aliasing guarantee the decimator actually provides.
#
# Uses the SAME coefficients as the C++ build (tools/fir_coeffs.json ==
# sdr_adapter/fir_coeffs.h).  Output: docs/resampler_response.png.
#
# Run: radioconda python tools/plot_resampler_response.py

import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from scipy.signal import freqz

HERE = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.abspath(os.path.join(HERE, "..", "docs"))

FS_OUT = 128000
PASS = 50000.0
STOP = 64000.0
WOR_N = 1 << 16


def load_specs():
    with open(os.path.join(HERE, "fir_coeffs.json")) as f:
        return json.load(f)


def alias_suppression(coeffs, fs_in, fs_out, n_out=4096):
    """Worst-case leakage into each output bin from OUT-OF-BAND input images.

    The in-band image (k=0) is the signal itself and must pass; the anti-aliasing
    guarantee is that every folded image k>=1 (input freq f_out + k*fs_out, all
    above the output Nyquist) is suppressed by the FIR.  So we take the max over
    k>=1 only.
    """
    w, h = freqz(coeffs, worN=WOR_N, fs=fs_in)
    h = np.abs(h)
    f_out = np.linspace(0.0, fs_out / 2.0, n_out)
    supp = np.zeros_like(f_out)
    for k in range(1, int(fs_in / 2.0 // fs_out) + 2):
        f_img = f_out + k * fs_out
        ok = f_img <= fs_in / 2.0
        if not np.any(ok):
            continue
        val = np.interp(f_img[ok], w, h)
        supp[ok] = np.maximum(supp[ok], val)
    return f_out, supp


def main():
    data = load_specs()
    specs = data["specs"]
    fig, axes = plt.subplots(len(specs), 2, figsize=(12, 3.6 * len(specs)))
    if len(specs) == 1:
        axes = axes[np.newaxis, :]

    for ax_row, s in zip(axes, specs):
        fs_in = s["fs_in_hz"]
        coeffs = np.array(s["coeffs"], dtype=np.float64)

        # magnitude response
        w, h = freqz(coeffs, worN=WOR_N, fs=fs_in)
        h_db = 20.0 * np.log10(np.abs(h) + 1e-15)
        ax_row[0].plot(w / 1e3, h_db, lw=1.0, color="tab:blue")
        ax_row[0].axvline(PASS / 1e3, ls="--", lw=1.0, color="tab:green",
                          label=f"passband {PASS/1e3:.0f} kHz")
        ax_row[0].axvline(STOP / 1e3, ls="--", lw=1.0, color="tab:red",
                          label=f"stopband {STOP/1e3:.0f} kHz")
        ax_row[0].axhline(-70.0, ls=":", lw=1.0, color="gray", label="-70 dB")
        ax_row[0].set_title(f"{s['name']} FIR response (fs_in={fs_in/1e6:.2f} MHz)")
        ax_row[0].set_xlabel("frequency (kHz)")
        ax_row[0].set_ylabel("|H(f)| (dB)")
        ax_row[0].set_ylim(-100, 5)
        ax_row[0].grid(True, alpha=0.3)
        ax_row[0].legend(fontsize=8)

        # alias suppression
        f_out, supp = alias_suppression(coeffs, fs_in, FS_OUT)
        supp_db = 20.0 * np.log10(supp + 1e-15)
        ax_row[1].plot(f_out / 1e3, supp_db, lw=1.0, color="tab:orange")
        ax_row[1].axhline(-70.0, ls=":", lw=1.0, color="gray", label="-70 dB")
        ax_row[1].set_title(
            f"{s['name']} alias suppression into output bin "
            f"(min {np.min(supp_db):.1f} dB)")
        ax_row[1].set_xlabel("output frequency f_out (kHz, 0..64 kHz)")
        ax_row[1].set_ylabel("worst-case alias |H| (dB)")
        ax_row[1].set_ylim(-100, 5)
        ax_row[1].grid(True, alpha=0.3)
        ax_row[1].legend(fontsize=8)

    fig.tight_layout()
    os.makedirs(DOCS_DIR, exist_ok=True)
    out = os.path.join(DOCS_DIR, "resampler_response.png")
    fig.savefig(out, dpi=150)
    print("wrote", out)

    for s in specs:
        fs_in = s["fs_in_hz"]
        coeffs = np.array(s["coeffs"], dtype=np.float64)
        _, supp = alias_suppression(coeffs, fs_in, FS_OUT)
        print(f"[{s['name']}] alias suppression floor = "
              f"{20*np.log10(np.max(supp)+1e-15):.1f} dB")


if __name__ == "__main__":
    main()
