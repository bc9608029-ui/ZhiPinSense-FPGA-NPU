#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Temporary exploration: does settling-region DC-offset removal fix the collapse?"""
from __future__ import annotations
import hashlib, subprocess, sys, tempfile, os
from pathlib import Path
import numpy as np

CONTRACT_DIR = r"F:\嵌赛\fix10class24_independent_rx_delivery_fix1_work\scripts"
FIX2_DIR = r"F:\嵌赛\fix10class24_independent_rx_recovery_fix2_work\scripts"
sys.path.insert(0, CONTRACT_DIR)
sys.path.insert(0, FIX2_DIR)

import radioml_independent_rx_contract as IRX
import radioml_dualsdr_common as C
from reproduce_fix2_diagnosis import read_raw_i16, locate_preamble, FS, K_TOTAL
from radioml_independent_rx_recovery_fix2 import (
    estimate_public_reference_fix2, frac_delay_sinc)

# v2 amplitude contract (source_id = fix1v2-waveform-corrected-24waveforms)
V2_TX_SCALE = 71.609111379029812
V2_UNSCALE = 1.0 / V2_TX_SCALE
PI = 3.141592653589793238462643383279502884

LABELS = ["OOK","4ASK","8ASK","BPSK","QPSK","8PSK","16PSK","32PSK","16APSK",
          "32APSK","64APSK","128APSK","16QAM","32QAM","64QAM","128QAM","256QAM",
          "AM-SSB-WC","AM-SSB-SC","AM-DSB-WC","AM-DSB-SC","FM","GMSK","OQPSK"]

CAP = Path(r"F:\嵌赛\board_capture\rml24_fix2_dual_1773374951_244")
MODEL_DIR = r"F:\嵌赛\fix10class24_original_radioml_npu_ab1_work\sdr_rml24_fix10class24_original_radioml_npu_ab1\model_rml24_bf16"
MODEL_JSON = os.path.join(MODEL_DIR, "rml24_adamrv11_bf16.json")
MODEL_RAW = os.path.join(MODEL_DIR, "rml24_adamrv11_bf16.raw")
ICRAFT = r"D:\icraft\bin\icraft-run.exe"

def sha(b): return hashlib.sha256(b).hexdigest()

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

def derot(x, cfo, start=0):
    n = np.arange(len(x), dtype=np.float64) + start
    ph = -2.0 * PI * cfo * n / FS
    return x * (np.cos(ph) + 1j * np.sin(ph))

def recover(rx, est, unscale=V2_UNSCALE):
    timing = est["timing_offset"]
    aligned = np.roll(rx, -timing) if timing else rx
    rx_derot = derot(aligned, est["coarse_cfo_hz"])
    payload = rx_derot[IRX.K_PAYLOAD_START:IRX.K_PAYLOAD_START + IRX.K_PAYLOAD_COMPLEX]
    wl = IRX.wide_linear_inverse(payload, est["a"], est["b"])
    shifted = frac_delay_sinc(wl, -est["fractional_timing"])
    return shifted[:IRX.GEN.SAMPLE_LENGTH] * unscale

def recover_dcfix(rx, est, unscale=V2_UNSCALE):
    timing = est["timing_offset"]
    aligned = np.roll(rx, -timing) if timing else rx
    d = aligned[1024:2048].mean()          # settling-zero (silence) => LO leakage DC
    aligned = aligned - d
    rx_derot = derot(aligned, est["coarse_cfo_hz"])
    payload = rx_derot[IRX.K_PAYLOAD_START:IRX.K_PAYLOAD_START + IRX.K_PAYLOAD_COMPLEX]
    wl = IRX.wide_linear_inverse(payload, est["a"], est["b"])
    shifted = frac_delay_sinc(wl, -est["fractional_timing"])
    return shifted[:IRX.GEN.SAMPLE_LENGTH] * unscale

def tobytes(iq):
    x = np.empty((2, len(iq)), dtype="<f4")
    x[0] = iq.real.astype("<f4"); x[1] = iq.imag.astype("<f4")
    return x.tobytes()

# board recorded tensor SHA
board_shas = {}
for ln in (CAP / "board_independent_rx_results.tsv").read_text(encoding="utf-8").splitlines()[1:]:
    f = ln.rstrip("\n").split("\t")
    board_shas[int(f[0])] = f[-1]  # model_input_sha256

print("sid class          base_match  offset_removed   base_pred  dcfix_pred  dcfix_ok")
ok_base = ok_dc = 0
match = 0
for sid in range(1, 25):
    inter = read_raw_i16(CAP / ("%d.raw.i16" % sid))
    rx_full = C.deinterleave_int16(inter)
    off, _ = locate_preamble(rx_full, len(rx_full) - K_TOTAL)
    rx_burst = rx_full[off:off + K_TOTAL].copy()
    est = estimate_public_reference_fix2(rx_burst)
    base = recover(rx_burst, est)
    dc = recover_dcfix(rx_burst, est)
    if sha(tobytes(base)) == board_shas[sid]:
        match += 1
    timing = est["timing_offset"]
    aligned = np.roll(rx_burst, -timing) if timing else rx_burst
    d = aligned[1024:2048].mean()
    pb = int(np.argmax(infer(base)))
    pd = int(np.argmax(infer(dc)))
    ok_base += (pb == sid - 1); ok_dc += (pd == sid - 1)
    print("%3d %-12s %s  off=%.2f%+.2fj  base=%2d  dcfix=%2d  %s" % (
        sid, LABELS[sid-1], "MATCH" if sha(tobytes(base)) == board_shas[sid] else "MISS",
        d.real, d.imag, pb, pd, "CORRECT" if pd == sid-1 else ""))
print()
print("base tensor SHA match board: %d/24" % match)
print("baseline correct: %d/24   dcfix correct: %d/24" % (ok_base, ok_dc))
