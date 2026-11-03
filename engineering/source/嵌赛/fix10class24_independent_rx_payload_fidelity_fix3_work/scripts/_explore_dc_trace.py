#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Temporary: trace where the spurious DC enters the recovery chain (one frame)."""
from __future__ import annotations
import sys
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
V2_UNSCALE = 1.0 / 71.609111379029812
PI = 3.141592653589793238462643383279502884

def derot(x, cfo, start=0):
    n = np.arange(len(x), dtype=np.float64) + start
    ph = -2.0 * PI * cfo * n / FS
    return x * (np.cos(ph) + 1j*np.sin(ph))

for sid in (4, 18, 19):
    inter = read_raw_i16(CAP / ("%d.raw.i16" % sid))
    rx_full = C.deinterleave_int16(inter)
    off, _ = locate_preamble(rx_full, len(rx_full) - K_TOTAL)
    rx_burst = rx_full[off:off + K_TOTAL].copy()
    est = estimate_public_reference_fix2(rx_burst)
    aligned = np.roll(rx_burst, -est["timing_offset"]) if est["timing_offset"] else rx_burst

    # segment means (raw int16 counts domain)
    settle = aligned[1024:2048]
    train = aligned[2048:3072]
    payload = aligned[3072:3072+53760]
    print("=== sid=%d (cfo=%.1f tau=%.2f a=%.3f%+.3fj b=%.3f%+.3fj denom=%.5f) ===" % (
        sid, est["coarse_cfo_hz"], est["fractional_timing"],
        est["a"].real, est["a"].imag, est["b"].real, est["b"].imag,
        abs(est["a"])**2 - abs(est["b"])**2))
    print("  aligned settle[1024:2048] mean=%.3f%+.3fj  rms=%.3f" % (
        settle.mean().real, settle.mean().imag, np.sqrt(np.mean(np.abs(settle-settle.mean())**2))))
    print("  aligned train[2048:3072]  mean=%.3f%+.3fj  rms=%.3f" % (
        train.mean().real, train.mean().imag, np.sqrt(np.mean(np.abs(train-train.mean())**2))))
    print("  aligned payload[3072:]     mean=%.3f%+.3fj  rms=%.3f" % (
        payload.mean().real, payload.mean().imag, np.sqrt(np.mean(np.abs(payload-payload.mean())**2))))

    # after derot
    derot_b = derot(aligned, est["coarse_cfo_hz"])
    dp = derot_b[3072:3072+53760]
    print("  derot   payload mean=%.3f%+.3fj" % (dp.mean().real, dp.mean().imag))

    # after wide_linear_inverse
    wl = IRX.wide_linear_inverse(dp, est["a"], est["b"])
    print("  wl      payload mean=%.4f%+.4fj  first1024 mean=%.4f%+.4fj" % (
        wl.mean().real, wl.mean().imag, wl[:1024].mean().real, wl[:1024].mean().imag))

    # settle-region mean in raw domain -> what does it map to in wl domain?
    d_settle = settle.mean()
    print("  settle mean in raw counts: %.3f%+.3fj  -> maps via /denom*unscale ~= %.3f%+.3fj" % (
        d_settle.real, d_settle.imag,
        (d_settle.real / (abs(est['a'])**2-abs(est['b'])**2) * V2_UNSCALE).real,
        (d_settle.imag / (abs(est['a'])**2-abs(est['b'])**2) * V2_UNSCALE).imag))

    # recovered tensor (normalized)
    shifted = frac_delay_sinc(wl, -est["fractional_timing"])
    rec = shifted[:1024] * V2_UNSCALE
    print("  recovered tensor mean=%.4f%+.4fj  rms=%.4f" % (
        rec.mean().real, rec.mean().imag, np.sqrt(np.mean(np.abs(rec)**2))))
    print()
