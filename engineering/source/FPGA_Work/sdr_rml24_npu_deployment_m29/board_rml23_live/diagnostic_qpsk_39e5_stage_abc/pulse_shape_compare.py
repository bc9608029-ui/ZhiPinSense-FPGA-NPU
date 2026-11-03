#!/usr/bin/env python3
"""pulse_shape_compare.py -- direct pulse-shape / spectral-envelope comparison
between RadioML synthetic QPSK and the 78 real QPSK frames.

Reads the already-computed per-domain aggregates in out/domain_comparison.json
(psd_mean, envelope_sq_spec_mean), which were produced from the raw IQ, and
extracts the *direct* pulse-shaping evidence:

  1. |P(f)| spectral envelope  = sqrt(mean PSD)   (PSD ~ |pulse(f)|^2)
  2. pulse autocorrelation     = IFFT(mean PSD)   (Wiener-Khinchin)
  3. symbol rate               = peak of |x|^2 spectrum (cyclostationary)
  4. fractional bandwidths     = BW / symbol-rate  (isolates pulse shape from Rs)

No model inference, no training, no board access.  Pure read-only numpy.
"""
from __future__ import annotations

import json
import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")
FS = 128000.0
N = 1024
BIN_HZ = FS / N


def load():
    with open(os.path.join(OUT, "domain_comparison.json"), encoding="utf-8") as f:
        return json.load(f)


def single_sided_psd(psd_mean):
    psd = np.asarray(psd_mean, dtype=np.float64)
    psd_s = np.fft.fftshift(psd)
    freqs = np.fft.fftshift(np.fft.fftfreq(N, 1.0 / FS))
    pos = freqs >= 0
    return freqs[pos], psd_s[pos]


def bw_hz(freqs, pn, db):
    """Highest positive frequency at which normalized power >= 10**(-db/10)."""
    thr = 10.0 ** (-db / 10.0)
    idx = np.where(pn >= thr)[0]
    if len(idx) == 0:
        return 0.0
    return float(freqs[idx[-1]])


def analyze(name, psd_mean, env_sq_mean):
    f, p = single_sided_psd(psd_mean)
    pn = p / p.max()

    bws = {db: bw_hz(f, pn, db) for db in (3, 6, 20, 40)}

    # cyclostationary symbol rate: peak of averaged |x|^2 spectrum (excl DC)
    es = np.asarray(env_sq_mean, dtype=np.float64)
    es_s = np.fft.fftshift(es)
    f_all = np.fft.fftshift(np.fft.fftfreq(N, 1.0 / FS))
    pos = f_all >= 0
    ef, e = f_all[pos], es_s[pos]
    e[0] = 0.0
    half = len(e) // 2
    pk = int(np.argmax(e[1:half])) + 1
    rs = float(ef[pk])
    med = float(np.median(e[1:half]))
    prominence = float(e[pk] / (med + 1e-300))

    # pulse autocorrelation via IFFT of mean PSD (Wiener-Khinchin)
    ac = np.fft.ifft(np.asarray(psd_mean, dtype=np.float64)).real
    ac = np.fft.fftshift(ac)
    ac = ac / (np.max(np.abs(ac)) + 1e-300)

    # main-lobe half-width at amplitude 0.5 (full width = 2*halfw samples)
    center = N // 2
    halfw = None
    for k in range(1, N // 2):
        if ac[center + k] < 0.5 and ac[center - k] < 0.5:
            halfw = k
            break

    return {
        "name": name,
        "symbol_rate_hz": rs,
        "symbol_rate_prominence": prominence,
        "bw_hz": bws,
        "bw20_over_bw3": bws[20] / bws[3] if bws[3] else None,
        "bw40_over_bw3": bws[40] / bws[3] if bws[3] else None,
        "bw3_fractional": bws[3] / rs if rs else None,   # BW3 / Rs (Nyquist=0.5)
        "bw20_fractional": bws[20] / rs if rs else None,
        "autocorr_mainlobe_halfwidth_samples": halfw,
        "autocorr_mainlobe_fullwidth_hz": 2.0 * halfw * BIN_HZ if halfw else None,
        "psd_norm": pn.tolist(),
        "autocorr_central": ac[center - 80: center + 80].tolist(),
    }


def main():
    dc = load()
    rm = analyze("RadioML_QPSK_30dB", dc["radioml"]["stats"]["psd_mean"],
                 dc["radioml"]["stats"]["envelope_sq_spec_mean"])
    re = analyze("Real_QPSK_78", dc["real"]["stats"]["psd_mean"],
                 dc["real"]["stats"]["envelope_sq_spec_mean"])

    result = {"fs": FS, "n_fft": N, "radioml": rm, "real": re}
    with open(os.path.join(OUT, "pulse_shape_compare.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    # ---- console summary ----
    def row(k, a, b, unit=""):
        print("%-32s rm=%12s  real=%12s  %s" % (k, _fmt(a), _fmt(b), unit))

    def _fmt(v):
        if v is None:
            return "n/a"
        return "%.4g" % v

    print("=== PULSE-SHAPE / SPECTRAL-ENVELOPE COMPARISON ===")
    print("symbol rate (cyclo) : rm=%.4g  real=%.4g Hz" % (rm["symbol_rate_hz"], re["symbol_rate_hz"]))
    print("symbol-line promin.  : rm=%.4g  real=%.4g" % (rm["symbol_rate_prominence"], re["symbol_rate_prominence"]))
    for db in (3, 6, 20, 40):
        row("PSD -%ddB bandwidth" % db, rm["bw_hz"][db], re["bw_hz"][db], "Hz")
    row("BW20/BW3 (rolloff) ", rm["bw20_over_bw3"], re["bw20_over_bw3"])
    row("BW40/BW3 (rolloff) ", rm["bw40_over_bw3"], re["bw40_over_bw3"])
    row("BW3 / Rs (fractional)", rm["bw3_fractional"], re["bw3_fractional"], "(Nyquist=0.5)")
    row("BW20 / Rs           ", rm["bw20_fractional"], re["bw20_fractional"])
    row("autocorr mainlobe   ", rm["autocorr_mainlobe_halfwidth_samples"],
        re["autocorr_mainlobe_halfwidth_samples"], "samples (half)")
    print()
    print("wrote", os.path.join(OUT, "pulse_shape_compare.json"))

    # ---- figure ----
    f_pos, p_rm = single_sided_psd(dc["radioml"]["stats"]["psd_mean"])
    _, p_re = single_sided_psd(dc["real"]["stats"]["psd_mean"])
    ac_rm = np.asarray(rm["autocorr_central"])
    ac_re = np.asarray(re["autocorr_central"])
    lags = np.arange(-80, 80)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))
    ax1.plot(f_pos / 1e3, 10 * np.log10(p_rm / p_rm.max() + 1e-300),
             label="RadioML QPSK@30dB", lw=1.6)
    ax1.plot(f_pos / 1e3, 10 * np.log10(p_re / p_re.max() + 1e-300),
             label="Real QPSK (78 frames)", lw=1.6)
    ax1.axvline(6.75, color="C0", ls=":", alpha=0.6)
    ax1.axvline(8.0, color="C1", ls=":", alpha=0.6)
    ax1.set_xlim(0, 40)
    ax1.set_ylim(-50, 2)
    ax1.set_xlabel("frequency (kHz)")
    ax1.set_ylabel("normalized PSD (dB)")
    ax1.set_title("Pulse spectral envelope  |P(f)|^2")
    ax1.legend(loc="upper right")
    ax1.grid(alpha=0.25)

    ax2.plot(lags, ac_rm, label="RadioML QPSK@30dB", lw=1.6)
    ax2.plot(lags, ac_re, label="Real QPSK (78 frames)", lw=1.6)
    ax2.set_xlabel("lag (samples)")
    ax2.set_ylabel("normalized autocorrelation")
    ax2.set_title("Pulse autocorrelation  (IFFT of PSD)")
    ax2.legend(loc="upper right")
    ax2.grid(alpha=0.25)

    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_pulse_shape.png"), dpi=130)
    print("wrote", os.path.join(OUT, "fig_pulse_shape.png"))


if __name__ == "__main__":
    main()
