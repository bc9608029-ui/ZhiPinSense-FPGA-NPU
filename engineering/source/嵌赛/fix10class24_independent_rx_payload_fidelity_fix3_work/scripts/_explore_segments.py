#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Temporary: segment derot payload + wl output to find the transient injection."""
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
from radioml_independent_rx_recovery_fix2 import estimate_public_reference_fix2

CAP = Path(r"F:\嵌赛\board_capture\rml24_fix2_dual_1773374951_244")
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
    derot_b = derot(aligned, est["coarse_cfo_hz"])
    payload = derot_b[3072:3072+53760]
    wl = IRX.wide_linear_inverse(payload, est["a"], est["b"])
    print("=== sid=%d ===" % sid)
    print("  derot payload segments (1024 each), mean real/imag:")
    for s in range(0, 6):
        seg = payload[s*1024:(s+1)*1024]
        print("    seg%d [%d:%d] mean=%8.3f%+8.3fj rms=%7.3f" % (
            s, s*1024, (s+1)*1024, seg.mean().real, seg.mean().imag,
            np.sqrt(np.mean(np.abs(seg)**2))))
    print("  wl output segments (1024 each), mean real/imag:")
    for s in range(0, 6):
        seg = wl[s*1024:(s+1)*1024]
        print("    seg%d [%d:%d] mean=%8.3f%+8.3fj rms=%7.3f" % (
            s, s*1024, (s+1)*1024, seg.mean().real, seg.mean().imag,
            np.sqrt(np.mean(np.abs(seg)**2))))
    print()
