#!/usr/bin/env python3
"""stage_b_domain_comparison.py -- RadioML synthetic QPSK vs 78 real QPSK frames,
same FP32 ONNX, same label order, no weight changes.

Produces DOMAIN_COMPARISON.json + figures + a compact human summary.  All
statistics are per-domain aggregates; nothing here modifies the model or data.

Run:  python stage_b_domain_comparison.py
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sys
from collections import Counter

import numpy as np
import h5py
import onnxruntime as ort

# ---- frozen identities / paths ----
HDF5 = r"F:/datasets/RadioML2018/GOLD_XYZ_OSC.0001_1024.hdf5"
IDX = r"F:/FPGA_Work/sdr_amr_rml24_ood_v1_1/data/radioml2018/rml24_split_indices.npz"
ONNX = r"F:/FPGA_Work/sdr_rml24_npu_deployment_m29/work/onnx/rml24_24class_opset17.onnx"
REAL = r"C:/Users/shado/Downloads/rml23_analysis_20261011_225430/rml23_capture_39e5_final_1773383076"
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")

LABEL_ORDER_24 = ("OOK","4ASK","8ASK","BPSK","QPSK","8PSK","16PSK","32PSK",
    "16APSK","32APSK","64APSK","128APSK","16QAM","32QAM","64QAM",
    "128QAM","256QAM","AM-SSB-WC","AM-SSB-SC","AM-DSB-WC",
    "AM-DSB-SC","FM","GMSK","OQPSK")

FS = 128000.0
N_FFT = 1024
BIN_HZ = FS / N_FFT


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def load_real():
    frames = []
    for p in sorted(glob.glob(os.path.join(REAL, "live_rx_tensor_*.f32"))):
        raw = open(p, "rb").read()
        d = np.frombuffer(raw, dtype="<f4")
        assert d.size == 2048
        iq = d.reshape(2, 1024).astype(np.float64)
        x = iq[0] + 1j * iq[1]
        fid = int(os.path.basename(p)[len("live_rx_tensor_"):-len(".f32")])
        frames.append({"frame_id": fid, "iq": iq, "x": x, "sha256": sha256_bytes(raw)})
    return frames


def load_radioml_qpsk(n_stats=300, snr=30.0):
    with np.load(IDX, allow_pickle=False) as z:
        ti, tl, ts = z["test_indices"], z["test_labels"], z["test_snrs"]
    mask = (tl == 4) & (np.abs(ts - snr) < 1e-6)
    sel = np.where(mask)[0][:n_stats]
    h5 = h5py.File(HDF5, "r"); X = h5["X"]
    out = []
    for k in sel:
        raw = np.asarray(X[int(ti[k])], dtype=np.float64)
        iq = raw.T
        out.append({"index": int(ti[k]), "iq": iq, "x": iq[0] + 1j * iq[1]})
    h5.close()
    return out


def _agg(vals):
    a = np.asarray(vals, dtype=np.float64)
    return {"mean": float(a.mean()), "std": float(a.std()),
            "min": float(a.min()), "max": float(a.max()),
            "median": float(np.median(a))}


def obw_bins(x, pct):
    ps = np.fft.fftshift(np.abs(np.fft.fft(x)) ** 2)
    total = float(ps.sum())
    if total <= 0:
        return 0
    thr = total * pct / 100.0
    pref = np.concatenate(([0.0], np.cumsum(ps)))
    best = N_FFT
    for lo in range(N_FFT):
        j = int(np.searchsorted(pref, pref[lo] + thr, side="left"))
        if j <= N_FFT and j > lo:
            best = min(best, j - lo)
    return best


def inst_freq(x):
    ph = np.unwrap(np.angle(x))
    dph = np.diff(ph)
    dph = (dph + np.pi) % (2 * np.pi) - np.pi
    return dph / (2 * np.pi) * FS


def cfo_hz_4th(x):
    y = x ** 4
    Y = np.fft.fft(y)
    f = np.fft.fftfreq(N_FFT, 1.0 / FS)
    pk = int(np.argmax(np.abs(Y)))
    return f[pk] / 4.0


def symrate_hz(x):
    sq = np.abs(x) ** 2
    sq = sq - sq.mean()
    S = np.abs(np.fft.fft(sq))
    # skip DC (bin 0) and its mirror
    S[0] = 0.0
    half = N_FFT // 2
    bins = np.arange(1, half)
    return float(bins[np.argmax(S[1:half])]) * BIN_HZ


def domain_stats(samples):
    """samples: list of dicts with 'x' (complex 1024) and 'iq' (2,1024)."""
    cr, i_rms, q_rms, peak, papr = [], [], [], [], []
    dc_i, dc_q, corr_iq = [], [], []
    quad = np.zeros(4)
    amp_hist = np.zeros(48)
    phase_hist = np.zeros(64)
    dph_all = []
    instf = []
    cfos, srates = [], []
    psd_sum = None
    ac_sum = None
    sqspec_sum = None
    for s in samples:
        x = s["x"]; iq = s["iq"]
        p = np.abs(x) ** 2
        cr.append(np.sqrt(p.mean()))
        i_rms.append(np.sqrt(np.mean(iq[0] ** 2)))
        q_rms.append(np.sqrt(np.mean(iq[1] ** 2)))
        peak.append(np.sqrt(p.max()))
        papr.append(10 * np.log10(p.max() / (p.mean() + 1e-300)))
        dc_i.append(iq[0].mean()); dc_q.append(iq[1].mean())
        corr_iq.append(float(np.corrcoef(iq[0], iq[1])[0, 1]))
        quad[0] += ((iq[0] >= 0) & (iq[1] >= 0)).sum()
        quad[1] += ((iq[0] < 0) & (iq[1] >= 0)).sum()
        quad[2] += ((iq[0] < 0) & (iq[1] < 0)).sum()
        quad[3] += ((iq[0] >= 0) & (iq[1] < 0)).sum()
        a = np.abs(x)
        amp_hist += np.histogram(a, bins=48, range=(0, 1.6))[0]
        ph = np.angle(x)
        phase_hist += np.histogram(ph, bins=64, range=(-np.pi, np.pi))[0]
        dph = np.angle(x[1:] * np.conj(x[:-1]))
        dph_all.append(dph)
        fi = inst_freq(x)
        instf.append(fi)
        cfos.append(cfo_hz_4th(x))
        srates.append(symrate_hz(x))
        P = np.abs(np.fft.fft(x)) ** 2
        psd_sum = P if psd_sum is None else psd_sum + P
        # autocorrelation (first 64 lags), normalized
        ac = np.correlate(x, x, mode="full")[N_FFT - 1: N_FFT - 1 + 64]
        ac_sum = ac if ac_sum is None else ac_sum + ac
        sq = np.abs(x) ** 2 - np.mean(np.abs(x) ** 2)
        S = np.abs(np.fft.fft(sq))
        sqspec_sum = S if sqspec_sum is None else sqspec_sum + S

    dph_all = np.concatenate(dph_all)
    instf = np.concatenate(instf)
    quad /= quad.sum()
    n = len(samples)
    return {
        "n": n,
        "complex_rms": _agg(cr),
        "i_rms": _agg(i_rms), "q_rms": _agg(q_rms),
        "peak": _agg(peak), "papr_db": _agg(papr),
        "dc_i_mean": _agg(dc_i), "dc_q_mean": _agg(dc_q),
        "iq_corr": _agg(corr_iq),
        "quadrant_occupancy": [float(v) for v in quad],
        "amp_histogram": amp_hist.tolist(),
        "phase_histogram": phase_hist.tolist(),
        "adjacent_phase_inc_deg": {
            "mean": float(np.rad2deg(dph_all.mean())),
            "std": float(np.rad2deg(dph_all.std()))},
        "inst_freq_hz": _agg(instf),
        "cfo_hz_4th": _agg(cfos),
        "symbol_rate_hz_cyclo": _agg(srates),
        "samples_per_symbol_est": float(FS / np.median(srates)),
        "psd_mean": (psd_sum / n).tolist(),
        "autocorr_mag_lags_64": np.abs(ac_sum / n).tolist(),
        "autocorr_phase_lags_64": np.angle(ac_sum / n).tolist(),
        "envelope_sq_spec_mean": (sqspec_sum / n).tolist(),
        "obw_bins": {
            "90": [obw_bins(s["x"], 90) for s in samples],
            "95": [obw_bins(s["x"], 95) for s in samples],
            "99": [obw_bins(s["x"], 99) for s in samples],
        },
    }


def obw_summary(st):
    out = {}
    for k, v in st["obw_bins"].items():
        a = np.array(v)
        out[k] = {"bins": _agg(a), "hz": _agg(a * BIN_HZ)}
    return out


def _build_inter_model(inter, oname):
    """Return a temp ONNX whose graph outputs include every intermediate
    activation of interest, so onnxruntime can return them via run()."""
    import onnx
    from onnx import helper, TensorProto
    m = onnx.load(ONNX)
    existing = set(o.name for o in m.graph.output)
    for name in inter:
        if name in existing or name == oname:
            continue
        m.graph.output.append(helper.make_tensor_value_info(name, TensorProto.FLOAT, None))
    tmp = os.path.join(OUT, "_tmp_inter_outputs.onnx")
    onnx.save(m, tmp)
    return tmp


def run_onnx(iq_list):
    import onnx
    from onnx import helper, TensorProto
    m = onnx.load(ONNX)
    oname = m.graph.output[0].name
    # intermediate tensor names (in graph order) for per-layer activation stats
    inter = []
    for n in m.graph.node:
        if n.op_type in ("Conv", "Relu", "Add", "ReduceMean", "Gemm"):
            for o in n.output:
                if o not in inter and o != oname:
                    inter.append(o)
    tmp = _build_inter_model(inter, oname)
    sess = ort.InferenceSession(tmp, providers=["CPUExecutionProvider"])
    iname = sess.get_inputs()[0].name
    outs = []
    act_acc = {name: [] for name in inter}
    for iq in iq_list:
        feeds = {iname: np.asarray(iq, dtype=np.float32)[None]}
        res = sess.run([oname] + inter, feeds)
        logits = res[0][0]
        outs.append(logits)
        for name, val in zip(inter, res[1:]):
            v = np.asarray(val).ravel()
            act_acc[name].append((float(np.sqrt(np.mean(v ** 2))), float(np.mean(v)),
                                  float(np.var(v)), float((v == 0.0).mean()),
                                  float(np.max(np.abs(v)))))
    act_stats = {}
    for name, vs in act_acc.items():
        r = np.array([v[0] for v in vs]); mu = np.array([v[1] for v in vs])
        var = np.array([v[2] for v in vs]); zf = np.array([v[3] for v in vs])
        mx = np.array([v[4] for v in vs])
        act_stats[name] = {"rms_mean": float(r.mean()), "mean_mean": float(mu.mean()),
                           "var_mean": float(var.mean()), "zero_frac_mean": float(zf.mean()),
                           "max_abs_mean": float(mx.mean())}
    try:
        os.remove(tmp)
    except OSError:
        pass
    return np.array(outs), act_stats, inter


def topk(logits, k=5):
    idx = np.argsort(logits)[::-1][:k]
    return [{"class": LABEL_ORDER_24[int(i)], "idx": int(i), "logit": float(logits[i])}
            for i in idx]


def main():
    os.makedirs(OUT, exist_ok=True)

    rm = load_radioml_qpsk(n_stats=300, snr=30.0)
    real = load_real()

    rm_stats = domain_stats(rm)
    real_stats = domain_stats(real)

    # ONNX on both domains (subset for speed: 200 RM, all 78 real)
    rm_logits, rm_act, inter = run_onnx([s["iq"] for s in rm[:200]])
    real_logits, real_act, _ = run_onnx([f["iq"] for f in real])

    rm_top1 = Counter(LABEL_ORDER_24[int(np.argmax(l))] for l in rm_logits)
    real_top1 = Counter(LABEL_ORDER_24[int(np.argmax(l))] for l in real_logits)

    # QPSK logit + prob statistics (softmax over 24)
    def softmax(l):
        e = np.exp(l - l.max()); return e / e.sum()
    rm_qpsk_logit = [float(l[4]) for l in rm_logits]
    real_qpsk_logit = [float(l[4]) for l in real_logits]
    rm_qpsk_prob = [float(softmax(l)[4]) for l in rm_logits]
    real_qpsk_prob = [float(softmax(l)[4]) for l in real_logits]

    result = {
        "label_order_24": list(LABEL_ORDER_24),
        "model_onnx_sha256": sha256_bytes(open(ONNX, "rb").read()),
        "radioml": {
            "source": "RadioML2018.01A test split, class QPSK (label 4), SNR=30dB",
            "n_samples": len(rm),
            "stats": rm_stats,
            "obw": obw_summary(rm_stats),
            "top1_histogram": dict(sorted(rm_top1.items())),
            "qpsk_logit": _agg(rm_qpsk_logit),
            "qpsk_prob": _agg(rm_qpsk_prob),
            "topk_example": topk(rm_logits[0]),
            "activation_rms": rm_act,
        },
        "real": {
            "source": "78 real external QPSK capture frames (final model input)",
            "n_samples": len(real),
            "stats": real_stats,
            "obw": obw_summary(real_stats),
            "top1_histogram": dict(sorted(real_top1.items())),
            "qpsk_logit": _agg(real_qpsk_logit),
            "qpsk_prob": _agg(real_qpsk_prob),
            "topk_example": topk(real_logits[0]),
            "activation_rms": real_act,
        },
        "input_sha256": [f["sha256"] for f in real],
        "radioml_indices_used": [s["index"] for s in rm],
    }
    with open(os.path.join(OUT, "domain_comparison.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)

    # ---- console summary ----
    def line(k, rm_v, real_v, unit=""):
        print("%-28s rm=%10s real=%10s %s" % (k, rm_v, real_v, unit))

    print("=== DOMAIN COMPARISON (RadioML QPSK@30dB vs 78 real QPSK) ===")
    print("complex RMS      : rm=%.5f  real=%.5f" % (rm_stats["complex_rms"]["mean"], real_stats["complex_rms"]["mean"]))
    print("scalar I RMS     : rm=%.5f  real=%.5f" % (rm_stats["i_rms"]["mean"], real_stats["i_rms"]["mean"]))
    print("scalar Q RMS     : rm=%.5f  real=%.5f" % (rm_stats["q_rms"]["mean"], real_stats["q_rms"]["mean"]))
    print("PAPR (dB)        : rm=%.3f  real=%.3f" % (rm_stats["papr_db"]["mean"], real_stats["papr_db"]["mean"]))
    print("DC I mean        : rm=%.6f  real=%.6f" % (rm_stats["dc_i_mean"]["mean"], real_stats["dc_i_mean"]["mean"]))
    print("DC Q mean        : rm=%.6f  real=%.6f" % (rm_stats["dc_q_mean"]["mean"], real_stats["dc_q_mean"]["mean"]))
    print("I/Q corr         : rm=%.5f  real=%.5f" % (rm_stats["iq_corr"]["mean"], real_stats["iq_corr"]["mean"]))
    print("quadrant occ     : rm=%s" % ["%.3f" % v for v in rm_stats["quadrant_occupancy"]])
    print("                 : real=%s" % ["%.3f" % v for v in real_stats["quadrant_occupancy"]])
    print("dPhase (deg)     : rm=%.3f  real=%.3f" % (rm_stats["adjacent_phase_inc_deg"]["mean"], real_stats["adjacent_phase_inc_deg"]["mean"]))
    print("inst freq (Hz)   : rm=%.3f  real=%.3f" % (rm_stats["inst_freq_hz"]["mean"], real_stats["inst_freq_hz"]["mean"]))
    print("CFO 4th (Hz)     : rm=%.3f  real=%.3f" % (rm_stats["cfo_hz_4th"]["mean"], real_stats["cfo_hz_4th"]["mean"]))
    print("sym rate (Hz)    : rm=%.1f  real=%.1f" % (rm_stats["symbol_rate_hz_cyclo"]["mean"], real_stats["symbol_rate_hz_cyclo"]["mean"]))
    print("sps (est)        : rm=%.2f  real=%.2f" % (rm_stats["samples_per_symbol_est"], real_stats["samples_per_symbol_est"]))
    print("OBW 90/95/99 (Hz): rm=%.0f/%.0f/%.0f  real=%.0f/%.0f/%.0f" % (
        rm_stats["obw_bins"]["90"][0] if False else np.median(rm_stats["obw_bins"]["90"]) * BIN_HZ,
        np.median(rm_stats["obw_bins"]["95"]) * BIN_HZ, np.median(rm_stats["obw_bins"]["99"]) * BIN_HZ,
        np.median(real_stats["obw_bins"]["90"]) * BIN_HZ, np.median(real_stats["obw_bins"]["95"]) * BIN_HZ,
        np.median(real_stats["obw_bins"]["99"]) * BIN_HZ))
    print("FP32 top-1 RM    :", dict(sorted(rm_top1.items())))
    print("FP32 top-1 REAL  :", dict(sorted(real_top1.items())))
    print("QPSK logit RM    : mean=%.3f  real=%.3f" % (np.mean(rm_qpsk_logit), np.mean(real_qpsk_logit)))
    print("QPSK prob  RM    : mean=%.4f  real=%.4f" % (np.mean(rm_qpsk_prob), np.mean(real_qpsk_prob)))
    print()
    print("wrote", os.path.join(OUT, "domain_comparison.json"))


if __name__ == "__main__":
    main()
