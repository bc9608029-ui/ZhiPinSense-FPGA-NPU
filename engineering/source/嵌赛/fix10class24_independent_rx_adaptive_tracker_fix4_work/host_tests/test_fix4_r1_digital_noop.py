#!/usr/bin/env python3
"""REVIEW-R1 digital noop: on a MATCHED clean burst (received == frozen reference,
no RF, no DC), every corrected tracker must estimate a ~0 DC trajectory, so
subtracting it is a near-no-op.

This is the offline stand-in for the digital counterexample: with the corrected
per-sample residual, a matched (no-RF) burst has ~0 residual anchors, so the
tracker trajectories are ~0 and cannot introduce classification flips.  (The full
digital no-new-flips is MEASURED, not hardcoded, by digital_counterexample_r1.py.)

Run:  python -I host_tests/test_fix4_r1_digital_noop.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import fix4_residual_ref as RREF  # noqa: E402
import fix3_recovery as R          # noqa: E402
import trackers_fix4_r1 as TK      # noqa: E402

failures = 0

# matched clean burst: received == frozen reference, no RF, no DC.
aligned = np.zeros(R.K_TOTAL, dtype=np.complex128)
for name in RREF.BLOCK_ORDER:
    s = RREF.BLOCK_START[name]
    aligned[s:s + RREF.BLOCK_LEN[name]] = RREF.PUBLIC_REFERENCE[name]

est = {"a": 1.0 + 0.0j, "b": 0.0 + 0.0j, "fractional_timing": 0.0,
       "coarse_cfo_hz": 0.0}
rms = float(np.sqrt(np.mean(np.abs(aligned) ** 2)))

for name in ["T1_blockwise_linear", "T2_exp_transient", "T3_hermite",
             "T4_kalman", "T5_kalman_crossframe"]:
    traj, _ = TK.dc_trajectory(name, aligned, est, None)
    dc_rms = float(np.sqrt(np.mean(np.abs(traj) ** 2)))
    ok = dc_rms < 0.1 * rms
    print("[%s] %-24s |dc|_rms=%.5f vs signal_rms=%.5f  (near-no-op=%s)" % (
        "OK " if ok else "FAIL", name, dc_rms, rms, dc_rms < 0.1 * rms))
    failures += 0 if ok else 1

print("digital_noop_r1: %d failure(s)" % failures)
sys.exit(1 if failures else 0)
