#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_common.py -- shared constants + measurement helpers for
fix10class24-threedomain-pairwise-audit1.

Domains:
  A        = original RadioML2018.01A  (training/eval distribution, real preprocessing)
  B_source = clean24 compatible generated signals (before digital D2 stage)
  B_d2     = B_source after the digital D2 build->quantize->restore chain (NO RF)
  C        = B after five rounds of real dual-SDR TX/RX + production recovery (WL)

Red lines: read-only on inputs; no board/SDR/re-capture/training; no model /
generator / preprocessor / recovery / threshold modification; no cherry-picking
by true label; snr_db=nan is NOT interpreted as a definite SNR.
"""
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

A_HDF5 = r"F:/datasets/RadioML2018/GOLD_XYZ_OSC.0001_1024.hdf5"
B_HDF5 = r"F:/嵌赛/fix10clean2a_dataset/clean24_formal12000.hdf5"
CLEAN24_SMOKE = (r"F:/嵌赛/fix10class24_tx_rms_sweep1_work/"
                 r"sdr_rml24_fix10class24_tx_rms_sweep1/clean24_smoke")
MANIFEST = os.path.join(CLEAN24_SMOKE, "route_d2_rf_manifest.tsv")
FULL24_EXPORT = (r"F:/嵌赛/fix10class24_full24_accuracy1_work/"
                 r"sdr_rml24_fix10class24_full24_accuracy1/results/"
                 r"full24_accuracy1/forced_classify_export/"
                 r"rml24_full24_accuracy1_1773372865")
REPEAT3_EXPORT = (r"F:/嵌赛/fix10class24_dualsdr_repeat3_audit1_work/"
                  r"results/forced_exports")

REPEAT3_ROUNDS = ("dual_bf16_rms2048_run1", "dual_bf16_rms2048_run2",
                  "dual_bf16_rms2048_run3")

# --------------------------------------------------------------------------
# Frozen identities (recorded from prior offline work; NOT re-derived here)
# --------------------------------------------------------------------------
FROZEN = {
    "model_json_sha256": "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42",
    "model_raw_sha256": "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151",
    "checkpoint_sha256": "96cd25f87d6f6f8cacda94432136db9420f74300cecba71df3c9fbe49817be6d",
    "a_hdf5_sha256": "e3dd0bef66a3426959ee66a1709a8c0a95d4f8395d18aaf6f1214bdbc763bd38",
    "split_indices_sha256": "9a035841baef299ac918ae64294d59ba2298c5f20852862d3dd4069547330335",
    "b_generator_sha256": "aa5fe816dbfddbd26512ac2240c504eccfe3769293aac2fbf2caf7c172fa76d5",
    "gate_residual_max": 0.100,
}

LABEL_ORDER_24 = [
    "OOK", "4ASK", "8ASK", "BPSK", "QPSK", "8PSK", "16PSK", "32PSK",
    "16APSK", "32APSK", "64APSK", "128APSK", "16QAM", "32QAM", "64QAM",
    "128QAM", "256QAM", "AM-SSB-WC", "AM-SSB-SC", "AM-DSB-WC", "AM-DSB-SC",
    "FM", "GMSK", "OQPSK",
]
N_CLASSES = 24
SOURCE_INDEXES = list(range(0, 12000, 500))  # 0,500,...,11500 (k=0 holdout)

MANIFEST_HEADER = [
    "sample_index", "source_index", "raw24_class", "deployed23_class",
    "modulation", "snr_db", "split_role", "global_K", "original_dc_i",
    "original_dc_q", "ac_rms", "rec_scale", "complex_count", "sample_rate",
    "tx_rms", "tx_peak", "clip_count", "edge_policy", "guard",
    "original_sha256", "quantized_sha256", "recovered_tensor_sha256",
    "quantized_file", "recovered_tensor_file",
]


# --------------------------------------------------------------------------
# IO helpers
# --------------------------------------------------------------------------
def sha256_file(path, nbytes=None):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        if nbytes is None:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        else:
            h.update(f.read(nbytes))
    return h.hexdigest()


def load_manifest():
    rows = {}
    with open(MANIFEST, "r", encoding="utf-8", newline="") as f:
        lines = [ln.rstrip("\r\n") for ln in f]
    assert lines[0].split("\t") == MANIFEST_HEADER, "manifest header changed"
    for ln in lines[1:]:
        if not ln.strip():
            continue
        f = ln.split("\t")
        rows[int(f[1])] = {
            "raw24_class": int(f[2]),
            "modulation": f[4],
            "snr_db": f[5],
            "original_dc_i": float(f[8]),
            "original_dc_q": float(f[9]),
            "ac_rms": float(f[10]),
            "rec_scale": float(f[11]),
            "tx_rms": float(f[14]),
            "tx_peak": float(f[15]),
            "original_sha256": f[19],
            "quantized_sha256": f[20],
            "recovered_tensor_sha256": f[21],
            "quantized_file": f[22],
            "recovered_tensor_file": f[23],
        }
    return rows


def load_tensor_2x1024(path):
    """Load a [2,1024] f32le file -> complex [1024] (row0=real, row1=imag)."""
    a = np.fromfile(path, dtype=np.float32)
    assert a.size == 2048, "%s has %d floats (want 2048)" % (path, a.size)
    x = a.reshape(2, 1024)
    return (x[0] + 1j * x[1]).astype(np.complex128)


# --------------------------------------------------------------------------
# Per-sample statistics (shared across domains)
# --------------------------------------------------------------------------
def sample_stats(iq):
    """Domain-agnostic stats of a single complex IQ frame (length 1024)."""
    iq = np.asarray(iq, dtype=np.complex128).ravel()
    n = iq.size
    p = np.abs(iq) ** 2
    mean_p = p.mean()
    rms = float(np.sqrt(mean_p))
    dc = float(np.abs(iq.mean()))
    papr_db = float(10.0 * np.log10(p.max() / mean_p)) if mean_p > 0 else float("inf")

    w = np.hanning(n)
    X = np.fft.fftshift(np.fft.fft(iq * w, n=4096))
    P = np.abs(X) ** 2
    total = P.sum()
    order = np.argsort(P)[::-1]
    csum = np.cumsum(P[order])
    bw99 = float((np.searchsorted(csum, 0.99 * total) + 1) / P.size)
    pmax = P.max()
    bw20 = float((P > pmax / 100.0).sum() / P.size)
    Ppos = P[P > 0]
    flatness = (float(np.exp(np.mean(np.log(Ppos))) / np.mean(Ppos))
                if Ppos.size else 0.0)

    ph = np.unwrap(np.angle(iq))
    ifr = float(np.mean(np.abs(np.diff(ph))) / (2.0 * np.pi))
    return dict(rms=rms, dc=dc, papr_db=papr_db, bw99=bw99, bw20=bw20,
                flatness=flatness, ifr=ifr)


def stats_fields():
    return ["rms", "dc", "papr_db", "bw99", "bw20", "flatness", "ifr"]


# --------------------------------------------------------------------------
# Pairwise (matched) complex-alignment metrics
# --------------------------------------------------------------------------
def aligned_metrics(ref, est):
    """Optimal complex LS gain alignment: est ~= g*ref + residual.

    Returns corr (|normalized inner product|), nmse (after g), gain_mag,
    gain_phase_deg, and raw rms/dc for both.
    """
    b = np.asarray(ref, dtype=np.complex128).ravel()
    c = np.asarray(est, dtype=np.complex128).ravel()
    bb = np.vdot(b, b).real
    cc = np.vdot(c, c).real
    bc = np.vdot(b, c)
    corr = float(abs(bc) / (np.sqrt(bb * cc))) if bb > 0 and cc > 0 else 0.0
    g = bc / bb if bb > 0 else 0.0
    resid = c - g * b
    nmse = float(np.vdot(resid, resid).real / cc) if cc > 0 else float("inf")
    gain_mag = float(abs(g))
    gain_phase = float(np.degrees(np.angle(g)))
    return dict(
        corr=corr, nmse=nmse, gain_mag=gain_mag, gain_phase_deg=gain_phase,
        rms_ref=float(np.sqrt(bb / b.size)), rms_est=float(np.sqrt(cc / c.size)),
        dc_ref=float(abs(b.mean())), dc_est=float(abs(c.mean())),
    )


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, sort_keys=True)
        f.write("\n")


def write_tsv(path, header, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\t".join(header) + "\n")
        for r in rows:
            f.write("\t".join("" if v is None else str(v) for v in r) + "\n")
