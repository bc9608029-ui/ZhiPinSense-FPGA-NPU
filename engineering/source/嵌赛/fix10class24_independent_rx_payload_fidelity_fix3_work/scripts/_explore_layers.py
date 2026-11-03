#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Temporary: localize recovered-vs-clean degradation (Phase B exploration)."""
from __future__ import annotations
import hashlib, subprocess, sys, tempfile, os
from pathlib import Path
import numpy as np

CONTRACT_DIR = r"F:\嵌赛\fix10class24_independent_rx_delivery_fix1_work\scripts"
FIX2_DIR = r"F:\嵌赛\fix10class24_independent_rx_recovery_fix2_work\scripts"
sys.path.insert(0, CONTRACT_DIR)
sys.path.insert(0, FIX2_DIR)

CAP = Path(r"F:\嵌赛\board_capture\rml24_fix2_dual_1773374951_244")
CLEAN_DIR = Path(r"F:\嵌赛\fix10class24_waveform_correct_v2_work\replay_out\layers")
MODEL_DIR = r"F:\嵌赛\fix10class24_original_radioml_npu_ab1_work\sdr_rml24_fix10class24_original_radioml_npu_ab1\model_rml24_bf16"
MODEL_JSON = os.path.join(MODEL_DIR, "rml24_adamrv11_bf16.json")
MODEL_RAW = os.path.join(MODEL_DIR, "rml24_adamrv11_bf16.raw")
ICRAFT = r"D:\icraft\bin\icraft-run.exe"

LABELS = ["OOK","4ASK","8ASK","BPSK","QPSK","8PSK","16PSK","32PSK","16APSK",
          "32APSK","64APSK","128APSK","16QAM","32QAM","64QAM","128QAM","256QAM",
          "AM-SSB-WC","AM-SSB-SC","AM-DSB-WC","AM-DSB-SC","FM","GMSK","OQPSK"]

def load_tensor(path):
    a = np.frombuffer(Path(path).read_bytes(), dtype="<f4")
    return a[:1024] + 1j*a[1024:]

def infer(iq):
    x = np.empty((2, len(iq)), dtype="<f4")
    x[0] = iq.real.astype("<f4"); x[1] = iq.imag.astype("<f4")
    with tempfile.TemporaryDirectory() as td:
        inp = os.path.join(td, "input.bin")
        open(inp, "wb").write(x.tobytes())
        lp = os.path.join(td, "logs")
        subprocess.run([ICRAFT, "--json", MODEL_JSON, "--raw", MODEL_RAW,
                        "--network", "model_24class", "--input", inp,
                        "--backends", "Host", "--dump_output", "--log_path", lp],
                       cwd=td, capture_output=True)
        return np.frombuffer(open(os.path.join(lp, "model_24class", "ftmpHQB", "922.ftmp"), "rb").read(), dtype="<f4")

def corr(a, b):
    a = a - a.mean(); b = b - b.mean()
    return abs(np.vdot(a, b)) / (np.linalg.norm(a)*np.linalg.norm(b))

print("sid class      corr      dc_rec        dc_clean   bestgain        resid_after_gain  resid_after_gain+dc | clean_pred rec_pred recDC_pred gainDC_pred")
for sid in range(1, 25):
    clean = load_tensor(CLEAN_DIR / ("%d.orig.tensor.bin" % sid))
    rec = load_tensor(CAP / ("%d.recovered.tensor.bin" % sid))
    c = corr(rec, clean)
    dcr = rec.mean(); dcc = clean.mean()
    # best complex gain clean->rec
    clean0 = clean - clean.mean()
    rec0 = rec - rec.mean()
    g = np.vdot(clean0, rec0) / np.vdot(clean0, clean0)
    resid = np.linalg.norm(rec0 - g*clean0) / np.linalg.norm(rec0)
    # after gain + offset: rec ~= g*clean + d
    d = rec.mean() - g*clean.mean()
    resid2 = np.linalg.norm(rec - g*clean - d) / np.linalg.norm(rec)
    preds = {}
    preds['clean'] = int(np.argmax(infer(clean)))
    preds['rec'] = int(np.argmax(infer(rec)))
    preds['recDC'] = int(np.argmax(infer(rec - rec.mean())))
    preds['gainDC'] = int(np.argmax(infer((rec - d)/g)))
    print("%3d %-10s %.3f  %7.2f%+7.2fj %7.2f%+7.2fj  %.3f%+.3fj  %.3f             %.3f          | %2d(%s) %2d(%s) %2d(%s) %2d(%s)" % (
        sid, LABELS[sid-1], c, dcr.real, dcr.imag, dcc.real, dcc.imag, g.real, g.imag,
        resid, resid2,
        preds['clean'], "C" if preds['clean']==sid-1 else "x",
        preds['rec'], "C" if preds['rec']==sid-1 else "x",
        preds['recDC'], "C" if preds['recDC']==sid-1 else "x",
        preds['gainDC'], "C" if preds['gainDC']==sid-1 else "x"))
