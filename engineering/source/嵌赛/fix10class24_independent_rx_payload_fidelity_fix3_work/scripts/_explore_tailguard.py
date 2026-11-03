#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Temporary: compare settling vs tail-guard DC + test tail-guard DC-removal fix."""
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
from radioml_independent_rx_recovery_fix2 import estimate_public_reference_fix2, frac_delay_sinc

CAP = Path(r"F:\嵌赛\board_capture\rml24_fix2_dual_1773374951_244")
MODEL_DIR = r"F:\嵌赛\fix10class24_original_radioml_npu_ab1_work\sdr_rml24_fix10class24_original_radioml_npu_ab1\model_rml24_bf16"
MODEL_JSON = os.path.join(MODEL_DIR, "rml24_adamrv11_bf16.json")
MODEL_RAW = os.path.join(MODEL_DIR, "rml24_adamrv11_bf16.raw")
ICRAFT = r"D:\icraft\bin\icraft-run.exe"
V2_UNSCALE = 1.0 / 71.609111379029812
PI = 3.141592653589793238462643383279502884

LABELS = ["OOK","4ASK","8ASK","BPSK","QPSK","8PSK","16PSK","32PSK","16APSK",
          "32APSK","64APSK","128APSK","16QAM","32QAM","64QAM","128QAM","256QAM",
          "AM-SSB-WC","AM-SSB-SC","AM-DSB-WC","AM-DSB-SC","FM","GMSK","OQPSK"]

# burst layout: preamble[0:1024] settling[1024:2048] training[2048:3072]
#               payload[3072:56832] guard-zero[56832:58880] tail[58880:59904]
PAYLOAD_START = 3072
PAYLOAD_END = 3072 + 53760
GUARD_START = PAYLOAD_END          # 56832
GUARD_END = 58880

def derot(x, cfo, start=0):
    n = np.arange(len(x), dtype=np.float64) + start
    ph = -2.0 * PI * cfo * n / FS
    return x * (np.cos(ph) + 1j*np.sin(ph))

def infer(iq):
    x = np.empty((2, len(iq)), dtype="<f4")
    x[0] = iq.real.astype("<f4"); x[1] = iq.imag.astype("<f4")
    with tempfile.TemporaryDirectory() as td:
        inp = os.path.join(td, "input.bin"); open(inp, "wb").write(x.tobytes())
        lp = os.path.join(td, "logs")
        subprocess.run([ICRAFT, "--json", MODEL_JSON, "--raw", MODEL_RAW,
                        "--network", "model_24class", "--input", inp,
                        "--backends", "Host", "--dump_output", "--log_path", lp],
                       cwd=td, capture_output=True)
        return np.frombuffer(open(os.path.join(lp, "model_24class", "ftmpHQB", "922.ftmp"), "rb").read(), dtype="<f4")

def recover(rx, est, d=None):
    timing = est["timing_offset"]
    aligned = np.roll(rx, -timing) if timing else rx
    if d is not None:
        aligned = aligned - d
    rx_derot = derot(aligned, est["coarse_cfo_hz"])
    payload = rx_derot[PAYLOAD_START:PAYLOAD_END]
    wl = IRX.wide_linear_inverse(payload, est["a"], est["b"])
    shifted = frac_delay_sinc(wl, -est["fractional_timing"])
    return shifted[:1024] * V2_UNSCALE

print("sid class      settle_mean      guard_mean       payload_mean    | base DC     guardfix DC  | base_pred guard_pred")
ok_base = ok_guard = 0
for sid in range(1, 25):
    inter = read_raw_i16(CAP / ("%d.raw.i16" % sid))
    rx_full = C.deinterleave_int16(inter)
    off, _ = locate_preamble(rx_full, len(rx_full) - K_TOTAL)
    rx_burst = rx_full[off:off + K_TOTAL].copy()
    est = estimate_public_reference_fix2(rx_burst)
    aligned = np.roll(rx_burst, -est["timing_offset"]) if est["timing_offset"] else rx_burst
    settle = aligned[1024:2048].mean()
    guard = aligned[GUARD_START:GUARD_END].mean()
    payload_m = aligned[PAYLOAD_START:PAYLOAD_END].mean()
    base = recover(rx_burst, est)
    gf = recover(rx_burst, est, d=guard)
    pb = int(np.argmax(infer(base)))
    pg = int(np.argmax(infer(gf)))
    ok_base += (pb == sid-1); ok_guard += (pg == sid-1)
    print("%3d %-10s %6.2f%+6.2fj %6.2f%+6.2fj %6.2f%+6.2fj | %5.2f%+5.2fj %5.2f%+5.2fj | %2d(%s) %2d(%s)" % (
        sid, LABELS[sid-1], settle.real, settle.imag, guard.real, guard.imag,
        payload_m.real, payload_m.imag,
        base.mean().real, base.mean().imag, gf.mean().real, gf.mean().imag,
        pb, "C" if pb==sid-1 else "x", pg, "C" if pg==sid-1 else "x"))
print()
print("baseline correct: %d/24   tail-guard-fix correct: %d/24" % (ok_base, ok_guard))
