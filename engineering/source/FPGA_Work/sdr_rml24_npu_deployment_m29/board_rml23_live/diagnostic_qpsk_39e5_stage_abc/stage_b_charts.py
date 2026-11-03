#!/usr/bin/env python3
"""stage_b_charts.py -- finalize DOMAIN_COMPARISON.json (spectral_summary) + charts.

Reads out/domain_comparison.json, computes the cyclostationary / PSD-bandwidth
summary that supersedes the raw symbol-rate median, re-loads a handful of raw
samples for the constellation plot, and writes PNG figures.  Read-only with
respect to the model and data.
"""
import glob
import json
import os

import numpy as np
import h5py
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HDF5 = r"F:/datasets/RadioML2018/GOLD_XYZ_OSC.0001_1024.hdf5"
IDX = r"F:/FPGA_Work/sdr_amr_rml24_ood_v1_1/data/radioml2018/rml24_split_indices.npz"
REAL = r"C:/Users/shado/Downloads/rml23_analysis_20261011_225430/rml23_capture_39e5_final_1773383076"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
FS = 128000.0
N = 1024
BIN = FS / N


def spectral_summary(doc, tag):
    st = doc[tag]["stats"]
    S = np.array(st["envelope_sq_spec_mean"])
    half = N // 2
    seg = S[1:half]
    order = np.argsort(seg)[::-1]
    P = np.fft.fftshift(np.array(st["psd_mean"]))
    tot = P.sum()
    c = np.cumsum(P)
    def bw(db):
        thr = 10 ** (-db / 10)
        lo = int(np.searchsorted(c, tot * thr / 2))
        hi = int(np.searchsorted(c, tot * (1 - thr / 2)))
        return (hi - lo) * BIN
    return {
        "env_sq_top_peak_hz": float((order[0] + 1) * BIN),
        "env_sq_second_peak_hz": float((order[1] + 1) * BIN),
        "env_sq_prominence_top_over_second": float(seg[order[0]] / seg[order[1]]),
        "env_sq_clean_symbol_line": bool(seg[order[0]] / seg[order[1]] > 1.5),
        "psd_3db_bw_hz": float(bw(3)),
        "psd_20db_bw_hz": float(bw(20)),
        "psd_40db_bw_hz": float(bw(40)),
    }


def load_constellation(n=5):
    rm = []
    with np.load(IDX, allow_pickle=False) as z:
        ti, tl, ts = z["test_indices"], z["test_labels"], z["test_snrs"]
    m = (tl == 4) & (np.abs(ts - 30) < 1e-6)
    sel = np.where(m)[0][:n]
    h5 = h5py.File(HDF5, "r")
    X = h5["X"]
    for k in sel:
        raw = np.asarray(X[int(ti[k])], dtype=np.float64)
        rm.append(raw[:, 0] + 1j * raw[:, 1])
    h5.close()
    real = []
    for p in sorted(glob.glob(os.path.join(REAL, "live_rx_tensor_*.f32")))[:n]:
        d = np.fromfile(p, dtype="<f4").reshape(2, 1024).astype(np.float64)
        real.append(d[0] + 1j * d[1])
    return rm, real


def inst_freq(x):
    ph = np.unwrap(np.angle(x))
    dph = np.diff(ph)
    dph = (dph + np.pi) % (2 * np.pi) - np.pi
    return dph / (2 * np.pi) * FS


def load_instfreq(n_rm=300):
    rm_fi, real_fi = [], []
    with np.load(IDX, allow_pickle=False) as z:
        ti, tl, ts = z["test_indices"], z["test_labels"], z["test_snrs"]
    m = (tl == 4) & (np.abs(ts - 30) < 1e-6)
    sel = np.where(m)[0][:n_rm]
    h5 = h5py.File(HDF5, "r")
    X = h5["X"]
    for k in sel:
        raw = np.asarray(X[int(ti[k])], dtype=np.float64)
        rm_fi.append(inst_freq(raw[:, 0] + 1j * raw[:, 1]))
    h5.close()
    for p in sorted(glob.glob(os.path.join(REAL, "live_rx_tensor_*.f32"))):
        d = np.fromfile(p, dtype="<f4").reshape(2, 1024).astype(np.float64)
        real_fi.append(inst_freq(d[0] + 1j * d[1]))
    return np.concatenate(rm_fi), np.concatenate(real_fi)


def main():
    jp = os.path.join(OUT, "domain_comparison.json")
    doc = json.load(open(jp, encoding="utf-8"))
    doc["radioml"]["spectral_summary"] = spectral_summary(doc, "radioml")
    doc["real"]["spectral_summary"] = spectral_summary(doc, "real")
    json.dump(doc, open(jp, "w", encoding="utf-8"), indent=2)
    print("spectral_summary radioml:", doc["radioml"]["spectral_summary"])
    print("spectral_summary real   :", doc["real"]["spectral_summary"])

    rm_s, real_s = load_constellation()
    freq = np.fft.fftshift(np.fft.fftfreq(N, 1.0 / FS))
    amp_bins = np.linspace(0, 1.6, 48 + 1)
    ph_bins = np.linspace(-np.pi, np.pi, 64 + 1)

    # 1. PSD (dB, normalized)
    plt.figure(figsize=(9, 4))
    for tag, label in (("radioml", "RadioML QPSK@30dB"), ("real", "real QPSK")):
        P = np.fft.fftshift(np.array(doc[tag]["stats"]["psd_mean"]))
        P = 10 * np.log10(P / P.max() + 1e-12)
        plt.plot(freq / 1000, P, label=label)
    plt.xlabel("frequency (kHz)"); plt.ylabel("PSD (dB, normalized)")
    plt.title("Power spectral density: RadioML QPSK vs real QPSK")
    plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(OUT, "fig_psd.png"), dpi=110); plt.close()

    # 2. constellation
    fig, ax = plt.subplots(1, 2, figsize=(9, 4.5))
    ax[0].scatter(rm_s[0].real, rm_s[0].imag, s=3, alpha=0.5)
    ax[0].set_title("RadioML QPSK @30dB (one 1024 frame)"); ax[0].set_aspect("equal")
    ax[1].scatter(real_s[0].real, real_s[0].imag, s=3, alpha=0.5, color="tab:orange")
    ax[1].set_title("real QPSK frame 10"); ax[1].set_aspect("equal")
    for a in ax: a.set_xlabel("I"); a.set_ylabel("Q"); a.grid(alpha=0.3)
    plt.tight_layout(); plt.savefig(os.path.join(OUT, "fig_constellation.png"), dpi=110); plt.close()

    # 3. amplitude histogram
    plt.figure(figsize=(9, 4))
    for tag, label in (("radioml", "RadioML QPSK@30dB"), ("real", "real QPSK")):
        h = np.array(doc[tag]["stats"]["amp_histogram"], dtype=float)
        h = h / h.sum()
        plt.plot(amp_bins[:-1] + (amp_bins[1] - amp_bins[0]) / 2, h, label=label)
    plt.xlabel("|x| amplitude"); plt.ylabel("density")
    plt.title("Amplitude histogram"); plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(OUT, "fig_amp_hist.png"), dpi=110); plt.close()

    # 4. phase histogram
    plt.figure(figsize=(9, 4))
    for tag, label in (("radioml", "RadioML QPSK@30dB"), ("real", "real QPSK")):
        h = np.array(doc[tag]["stats"]["phase_histogram"], dtype=float)
        h = h / h.sum()
        plt.plot(np.rad2deg(ph_bins[:-1] + (ph_bins[1] - ph_bins[0]) / 2), h, label=label)
    plt.xlabel("phase (deg)"); plt.ylabel("density")
    plt.title("Phase histogram"); plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(OUT, "fig_phase_hist.png"), dpi=110); plt.close()

    # 5. instantaneous frequency histogram (raw data, all samples)
    rm_fi, real_fi = load_instfreq()
    plt.figure(figsize=(9, 4))
    for fi, label in ((rm_fi, "RadioML QPSK@30dB"), (real_fi, "real QPSK")):
        h, e = np.histogram(fi, bins=80, range=(-80000, 80000), density=True)
        plt.plot((e[:-1] + e[1:]) / 2 / 1000, h, label=label)
    plt.xlabel("instantaneous frequency (kHz)"); plt.ylabel("density")
    plt.title("Instantaneous frequency histogram"); plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(OUT, "fig_inst_freq.png"), dpi=110); plt.close()

    # 6. |x|^2 cyclostationary spectrum
    plt.figure(figsize=(9, 4))
    for tag, label in (("radioml", "RadioML QPSK@30dB"), ("real", "real QPSK")):
        S = np.array(doc[tag]["stats"]["envelope_sq_spec_mean"])
        S = S / S.max()
        plt.plot(np.arange(N) * BIN / 1000, S, label=label)
    plt.xlabel("frequency (kHz)"); plt.ylabel("|FFT(|x|^2 - mean)| (normalized)")
    plt.title("Envelope-squared (cyclostationary) spectrum: clean 16 kHz line vs smeared")
    plt.axvline(16, color="r", ls="--", lw=1, label="16 kHz symbol rate")
    plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(OUT, "fig_env_sq_spec.png"), dpi=110); plt.close()

    # 7. autocorrelation magnitude (first 64 lags)
    plt.figure(figsize=(9, 4))
    for tag, label in (("radioml", "RadioML QPSK@30dB"), ("real", "real QPSK")):
        ac = np.array(doc[tag]["stats"]["autocorr_mag_lags_64"])
        ac = ac / ac[0]
        plt.plot(ac, label=label)
    plt.xlabel("lag (samples)"); plt.ylabel("|R(tau)| / |R(0)|")
    plt.title("Autocorrelation magnitude"); plt.legend(); plt.grid(alpha=0.3); plt.tight_layout()
    plt.savefig(os.path.join(OUT, "fig_autocorr.png"), dpi=110); plt.close()

    print("charts written to", OUT)


if __name__ == "__main__":
    main()
