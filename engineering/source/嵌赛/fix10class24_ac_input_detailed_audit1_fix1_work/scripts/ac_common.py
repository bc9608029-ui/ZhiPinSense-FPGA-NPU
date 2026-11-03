#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ac_common.py -- shared constants + full IQ feature metrics for
fix10class24-ac-input-detailed-audit1 (DIRECT A<->C feature audit).

Domains:
  A = original RadioML2018.01A (training/eval distribution; test split).
  C = real dual-SDR recovered model-input tensors (production wide-linear path,
      all diagnostic-gate-bypass; snr_db = nan).

Red lines (never violate):
  * pure offline; no board / SDR / re-capture / training / model / recovery /
    threshold modification;
  * NEVER substitute B<->C residual for A<->C -- this module does DIRECT A<->C;
  * C snr_db = nan is NOT interpreted as a definite SNR, and never matched to a
    specific A SNR stratum;
  * A and C are NOT the same symbol sequence -> NO pointwise subtraction /
    cross-sample correlation / NMSE-as-channel-recovery-error; comparison is
    DISTRIBUTIONAL / feature-level per class;
  * no tensor for a class -> INSUFFICIENT_DATA (never invent / substitute);
  * never write "feature differs therefore that feature caused the error".
"""
from __future__ import annotations

import os
import json
import hashlib
import numpy as np

# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------
WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(WORK, "cache")
RESULTS = os.path.join(WORK, "results")
FIGURES = os.path.join(WORK, "results", "figures")
DOCS = os.path.join(WORK, "docs")

A_HDF5 = r"F:/datasets/RadioML2018/GOLD_XYZ_OSC.0001_1024.hdf5"
SPLIT_NPZ = r"F:/FPGA_Work/sdr_amr_rml24_ood_v1_1/data/radioml2018/rml24_split_indices.npz"

# Frozen identity (inherited from prior offline audits; not re-derived here)
FROZEN_A_HDF5_SHA = "e3dd0bef66a3426959ee66a1709a8c0a95d4f8395d18aaf6f1214bdbc763bd38"
FROZEN_SPLIT_SHA = "9a035841baef299ac918ae64294d59ba2298c5f20852862d3dd4069547330335"
FROZEN_MODEL_JSON_SHA = "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42"
FROZEN_MODEL_RAW_SHA = "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151"
FROZEN_CKPT_SHA = "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d"

# HDF5 shape (authority)
HDF5_N = 2555904
HDF5_X_SHAPE = (HDF5_N, 1024, 2)
HDF5_SIZE_BYTES = 21449148312
HDF5_MTIME_NS = 1791042816000000000

LABEL_ORDER_24 = [
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
    "FM", "GMSK", "OQPSK",
]
N_CLASSES = 24

# C-domain enumeration (58 tensors) -- authority for this task
THREEDOMAIN_RESULTS = r"F:/嵌赛/fix10class24_threedomain_pairwise_audit1_work/results"
MATCHED_RF_SAMPLES = os.path.join(THREEDOMAIN_RESULTS, "matched_rf_samples.tsv")

FULL24_EXPORT = (
    r"F:/嵌赛/fix10class24_full24_accuracy1_work/"
    r"sdr_rml24_fix10class24_full24_accuracy1/results/"
    r"full24_accuracy1/forced_classify_export/rml24_full24_accuracy1_1773372865"
)
REPEAT3_EXPORT = (
    r"F:/嵌赛/fix10class24_dualsdr_repeat3_audit1_work/results/forced_exports"
)
REPEAT3_ROUNDS = ("dual_bf16_rms2048_run1", "dual_bf16_rms2048_run2",
                  "dual_bf16_rms2048_run3")

# Classification outcome sources (read-only)
FULL24_PER_SAMPLE = (
    r"F:/嵌赛/fix10class24_full24_accuracy1_work/"
    r"sdr_rml24_fix10class24_full24_accuracy1/results/"
    r"full24_accuracy1/per_sample_results.tsv"
)
REPEAT3_PER_SAMPLE = (
    r"F:/嵌赛/fix10class24_dualsdr_repeat3_audit1_work/results/per_sample_results.tsv"
)

# A-reference selection (TEST split, per class per SNR)
SELECT_SNRS = [0, 10, 20, 30]
PER_CLASS_SNR = 100
SELECT_SEED = 20261019

# Focus / control classes (raw24 class index)
FOCUS_CLASSES = {14: "64QAM", 15: "128QAM", 23: "OQPSK", 22: "GMSK"}
CONTROL_CLASSES = {16: "256QAM", 1: "4ASK", 2: "8ASK", 17: "AM-SSB-WC",
                   18: "AM-SSB-SC"}

# Phase low-amplitude dropout rule (fixed BEFORE computing phase increment)
PHASE_EPS_RATIO = 0.05  # drop samples with |x| < PHASE_EPS_RATIO * median(|x|)

# Spectral unification (same window / fft / normalization for every signal)
FFT_N = 4096
WINDOW = "hann"  # np.hanning(1024) applied before zero-pad FFT
SPECTRAL_FLOOR_REL = 1e-12  # RESERVED numeric constant (documented); NOT applied to flatness

# Autocorrelation lags
ACORR_LAGS = [1, 2, 4, 8, 16, 32]
ACORR_HALF_THRESH = 0.5

STATUS = "M29-RML24-FIX10CLASS24-AC-INPUT-DETAILED-AUDIT1-FIX1-COMPLETE"


# --------------------------------------------------------------------------
# IO helpers
# --------------------------------------------------------------------------
def sha256_file(path: str, nbytes: int | None = None) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        if nbytes is None:
            for chunk in iter(lambda: f.read(1 << 22), b""):
                h.update(chunk)
        else:
            h.update(f.read(nbytes))
    return h.hexdigest()


def load_tensor_2x1024(path: str) -> np.ndarray:
    """Load a [2,1024] f32le file -> complex [1024] (row0=real, row1=imag)."""
    a = np.fromfile(path, dtype=np.float32)
    assert a.size == 2048, "%s has %d floats (want 2048)" % (path, a.size)
    x = a.reshape(2, 1024)
    return (x[0] + 1j * x[1]).astype(np.complex128)


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")


def write_tsv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(header) + "\n")
        for r in rows:
            f.write("\t".join("" if v is None else str(v) for v in r) + "\n")


def read_tsv(path):
    with open(path, "r", encoding="utf-8", newline="") as f:
        lines = [ln.rstrip("\r\n") for ln in f]
    header = lines[0].split("\t")
    rows = []
    for ln in lines[1:]:
        if not ln.strip():
            continue
        rows.append(ln.split("\t"))
    return header, rows


# --------------------------------------------------------------------------
# Full per-frame feature set (base 7 + new; single unified FFT)
# --------------------------------------------------------------------------
BASE_FIELDS = ["rms", "dc", "papr_db", "bw99", "bw20", "flatness", "ifr"]


def _spectral(iq, window):
    """Unified window/FFT/PSD. Returns freq (cycles/sample), P (power), Pn."""
    n = iq.size
    w = np.hanning(n) if window == "hann" else np.ones(n)
    X = np.fft.fftshift(np.fft.fft(iq * w, n=FFT_N))
    freq = np.fft.fftshift(np.fft.fftfreq(FFT_N))
    P = np.abs(X) ** 2
    total = P.sum()
    Pn = P / total if total > 0 else np.zeros_like(P)
    return freq, P, Pn, total


def _bw99_continuous(freq, Pn, centroid):
    """Corrected 99% occupied bandwidth = FULL WIDTH of the smallest symmetric
    interval [centroid-b, centroid+b] containing 99% of total power
    (cycles/sample), via bisection. This is the CONTINUOUS-interval metric,
    distinct from the old bin-count 'bw99'."""
    lo, hi = 0.0, 0.5
    for _ in range(64):
        mid = 0.5 * (lo + hi)
        frac = Pn[np.abs(freq - centroid) <= mid].sum()
        if frac >= 0.99:
            hi = mid
        else:
            lo = mid
    return 2.0 * hi


def full_metrics(iq):
    """All scalar features of one complex IQ frame (length 1024)."""
    iq = np.asarray(iq, dtype=np.complex128).ravel()
    n = iq.size
    p = np.abs(iq) ** 2
    mean_p = float(p.mean())
    rms = float(np.sqrt(mean_p))
    mean_x = np.mean(iq)  # complex mean (keep real + imag)
    dc = float(abs(mean_x))
    papr_db = float(10.0 * np.log10(p.max() / mean_p)) if mean_p > 0 else float("inf")

    freq, P, Pn, total = _spectral(iq, WINDOW)

    # old bin-count bandwidth (kept SEPARATE, identical to threedomain audit_common)
    order = np.argsort(P)[::-1]
    csum = np.cumsum(P[order])
    bw99 = float((np.searchsorted(csum, 0.99 * total) + 1) / P.size)
    pmax = float(P.max())
    bw20 = float((P > pmax / 100.0).sum() / P.size)
    # flatness = geometric/arithmetic mean over P>0 bins. NO additive floor is
    # applied here (SPECTRAL_FLOOR_REL is a reserved numeric constant, NOT used),
    # matching the threedomain audit_common reference exactly.
    Ppos = P[P > 0]
    flatness = float(np.exp(np.mean(np.log(Ppos))) / np.mean(Ppos)) if Ppos.size else 0.0

    ph = np.unwrap(np.angle(iq))
    ifr = float(np.mean(np.abs(np.diff(ph))) / (2.0 * np.pi))

    # ---- amplitude / DC (new) ----
    amp = np.abs(iq)
    ac = iq - mean_x
    ac_rms = float(np.sqrt(np.mean(np.abs(ac) ** 2)))
    dc_i = float(mean_x.real)
    dc_q = float(mean_x.imag)
    dc_power_frac = float((abs(mean_x) ** 2) / mean_p) if mean_p > 0 else float("nan")
    amp_q = np.quantile(amp, [0.05, 0.25, 0.5, 0.75, 0.95])
    amp_skew = float(((amp - amp.mean()) ** 3).mean() / (amp.std() ** 3)) if amp.std() > 0 else float("nan")
    amp_kurt = float(((amp - amp.mean()) ** 4).mean() / (amp.std() ** 4) - 3.0) if amp.std() > 0 else float("nan")

    # ---- I/Q joint structure (new) ----
    ri = np.real(iq)
    rq = np.imag(iq)
    var_i = float(np.var(ri))
    var_q = float(np.var(rq))
    var_ratio = float(var_i / var_q) if var_q > 0 else float("inf")
    cov_iq = float(np.mean((ri - ri.mean()) * (rq - rq.mean())))
    corr_iq = float(cov_iq / np.sqrt(var_i * var_q)) if var_i > 0 and var_q > 0 else float("nan")
    pseudocov = np.mean(iq ** 2)  # complex E[x^2]
    noncirc = float(abs(pseudocov) / mean_p) if mean_p > 0 else float("nan")
    pseudocov_phase_deg = float(np.degrees(np.angle(pseudocov)))

    # ---- spectral (new) ----
    centroid = float((freq * Pn).sum())
    asym = float(Pn[freq > centroid].sum() - Pn[freq < centroid].sum())
    peak_bin = int(np.argmax(P))
    peak_freq = float(freq[peak_bin])
    outer = np.abs(freq) > 0.25
    noise_floor = float(np.median(P[outer])) if outer.sum() else 0.0
    peak_to_floor_db = float(10.0 * np.log10(pmax / noise_floor)) if noise_floor > 0 else float("inf")
    bw99_cont = _bw99_continuous(freq, Pn, centroid)

    # ---- time / phase (new) ----
    # Normalized complex-autocorrelation MAGNITUDE |E[x[n] conj(x[n-k])]| / E[|x|^2].
    # The numerator MUST stay COMPLEX until abs(): taking .real first wrongly nulls a
    # constant phase-shift term (a 0.25 cyc/sample tone has lag-1 magnitude 1023/1024,
    # but .real-first gives ~0).
    acorr = {}
    den = float(np.vdot(iq, iq).real)
    for k in ACORR_LAGS:
        num = np.vdot(iq[k:], iq[:-k])
        acorr["acorr_lag%d" % k] = float(abs(num) / den) if den > 0 else float("nan")
    acmag = [acorr["acorr_lag%d" % k] for k in ACORR_LAGS]
    half_lag = float("nan")
    for k, m in zip(ACORR_LAGS, acmag):
        if m < ACORR_HALF_THRESH:
            half_lag = float(k)
            break
    acorr["acorr_half_lag"] = half_lag

    # phase increment with low-amplitude dropout (eps = 5% of median |x|)
    eps = PHASE_EPS_RATIO * float(np.median(amp))
    valid = (amp[:-1] >= eps) & (amp[1:] >= eps)
    dphi = np.angle(iq[1:] * np.conj(iq[:-1]))
    phase_inc_mean = phase_inc_std = phase_inc_circ_mean = phase_inc_circ_std = float("nan")
    if valid.sum() >= 2:
        d = dphi[valid]
        phase_inc_mean = float(np.mean(d))
        phase_inc_std = float(np.std(d))
        R = float(min(1.0, abs(np.mean(np.exp(1j * d)))))
        phase_inc_circ_mean = float(np.angle(np.mean(np.exp(1j * d))))
        phase_inc_circ_std = float(np.sqrt(-2.0 * np.log(R))) if R > 0 else float("inf")

    amp_roc = np.abs(np.diff(amp))
    amp_roc_mean = float(amp_roc.mean())
    amp_roc_std = float(amp_roc.std())
    amp_roc_q90 = float(np.quantile(amp_roc, 0.9))

    nseg = 8
    seg = int(n // nseg)
    seg_rms = np.array([np.sqrt(np.mean(np.abs(iq[i * seg:(i + 1) * seg]) ** 2))
                        for i in range(nseg)])
    seg_power_mean = float(seg_rms.mean())
    seg_power_std = float(seg_rms.std())
    seg_power_cv = float(seg_power_std / seg_power_mean) if seg_power_mean > 0 else float("nan")
    seg_power_minmax = float(seg_rms.min() / seg_rms.max()) if seg_rms.max() > 0 else float("nan")

    out = {
        "rms": rms, "dc": dc, "papr_db": papr_db, "bw99": bw99, "bw20": bw20,
        "flatness": flatness, "ifr": ifr,
        "ac_rms": ac_rms, "dc_i": dc_i, "dc_q": dc_q, "dc_power_frac": dc_power_frac,
        "amp_q05": amp_q[0], "amp_q25": amp_q[1], "amp_q50": amp_q[2],
        "amp_q75": amp_q[3], "amp_q95": amp_q[4],
        "amp_skew": amp_skew, "amp_kurt": amp_kurt,
        "var_i": var_i, "var_q": var_q, "var_ratio": var_ratio,
        "cov_iq": cov_iq, "corr_iq": corr_iq, "noncirc": noncirc,
        "pseudocov_mag": abs(pseudocov), "pseudocov_phase_deg": pseudocov_phase_deg,
        "centroid": centroid, "asym": asym,
        "bw99_cont": bw99_cont, "peak_freq": peak_freq,
        "peak_to_floor_db": peak_to_floor_db,
        "phase_inc_mean": phase_inc_mean, "phase_inc_std": phase_inc_std,
        "phase_inc_circ_mean": phase_inc_circ_mean, "phase_inc_circ_std": phase_inc_circ_std,
        "amp_roc_mean": amp_roc_mean, "amp_roc_std": amp_roc_std, "amp_roc_q90": amp_roc_q90,
        "seg_power_mean": seg_power_mean, "seg_power_std": seg_power_std,
        "seg_power_cv": seg_power_cv, "seg_power_minmax": seg_power_minmax,
    }
    out.update(acorr)  # acorr_lag1..32 + acorr_half_lag
    return out


def metric_names():
    """Canonical metric ordering (base fields first)."""
    return list(full_metrics(np.zeros(8, dtype=np.complex128)).keys())


def is_finite_metrics(m):
    return all((not isinstance(v, float)) or np.isfinite(v) for v in m.values())
