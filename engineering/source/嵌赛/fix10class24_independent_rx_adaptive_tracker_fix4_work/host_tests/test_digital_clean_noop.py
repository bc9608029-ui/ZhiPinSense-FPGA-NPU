#!/usr/bin/env python3
"""Digital-regression proxy: on CLEAN data (zero-mean public blocks, no DC
drift), every tracker must estimate a ~0 DC trajectory (|dc| << signal RMS), so
subtracting it is a near-no-op that cannot introduce new classification flips.

This is the offline stand-in for "digital 23/24 with no new flips": the Fix4 DC
subtraction acts only on the RF recovery path and is byte-exact with the frozen
fix2 chain at T0 (test_m0_byterepro), so on clean data it degrades to ~identity.

Run:  python -I host_tests/test_digital_clean_noop.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import fix4_common as FC  # noqa: E402
import trackers_fix4 as TK  # noqa: E402

n = FC.K_TOTAL
failures = 0


def clean_burst():
    b = np.zeros(n, dtype=np.complex128)
    prng = np.random.default_rng(42)
    # zero-mean public blocks (16QAM / silence / ZC ~ zero mean), no drift
    for a, bb in [(FC.SETTLE_START, FC.SETTLE_END), (FC.TRAIN_START, FC.TRAIN_END),
                  (FC.GUARD_START, FC.GUARD_END), (FC.TAIL_START, FC.TAIL_END)]:
        b[a:bb] = 0.01 * (prng.standard_normal(bb - a) + 1j * prng.standard_normal(bb - a))
    # payload: a realistic unit-energy signal (clean, no DC)
    sig = prng.standard_normal(FC.PAYLOAD_END - FC.PAYLOAD_START) \
        + 1j * prng.standard_normal(FC.PAYLOAD_END - FC.PAYLOAD_START)
    b[FC.PAYLOAD_START:FC.PAYLOAD_END] = sig
    return b


aligned = clean_burst()
rms = float(np.sqrt(np.mean(np.abs(aligned) ** 2)))
for name in ["T1_blockwise_linear", "T2_exp_transient", "T3_hermite",
             "T4_kalman", "T5_kalman_crossframe"]:
    traj, _ = TK.dc_trajectory(name, aligned, None)
    dc_rms = float(np.sqrt(np.mean(np.abs(traj) ** 2)))
    ok = dc_rms < 0.1 * rms           # DC estimate is ~0 relative to signal RMS
    print("[%s] %-24s |dc|_rms=%.5f vs signal_rms=%.5f  (near-no-op=%s)" % (
        "OK " if ok else "FAIL", name, dc_rms, rms, dc_rms < 0.1 * rms))
    failures += 0 if ok else 1

print("digital_clean_noop: %d failure(s)" % failures)
sys.exit(1 if failures else 0)
