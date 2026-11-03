#!/usr/bin/env python3
"""Smoke test: every tracker (T0..T5 + C1) is finite, correct-length, payload-
independent and bounded on a synthetic burst with a scattered DC drift.

Run (isolated):
    python -I host_tests/test_trackers_smoke.py
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
rng = np.random.default_rng(12345)


def make_burst(payload_fill):
    aligned = np.zeros(n, dtype=np.complex128)
    # scattered, non-monotonic public DC (mirrors the real fix3 drift shape)
    dcs = {
        (FC.SETTLE_START, FC.SETTLE_END): complex(6.0, 3.0),
        (FC.TRAIN_START, FC.TRAIN_END): complex(-5.0, 4.0),
        (FC.GUARD_START, FC.GUARD_END): complex(7.0, -2.0),
        (FC.TAIL_START, FC.TAIL_END): complex(6.0, 5.0),
    }
    # public blocks are deterministic (fixed seed) so only the payload varies.
    prng = np.random.default_rng(999)
    for (a, b), dc in dcs.items():
        aligned[a:b] = dc + 0.01 * (prng.standard_normal(b - a)
                                    + 1j * prng.standard_normal(b - a))
    aligned[FC.PAYLOAD_START:FC.PAYLOAD_END] = payload_fill
    return aligned


payload_a = 0.05 * (rng.standard_normal(FC.PAYLOAD_END - FC.PAYLOAD_START)
                    + 1j * rng.standard_normal(FC.PAYLOAD_END - FC.PAYLOAD_START))
payload_b = 1000.0 + 100.0 * (rng.standard_normal(FC.PAYLOAD_END - FC.PAYLOAD_START)
                              + 1j * rng.standard_normal(FC.PAYLOAD_END - FC.PAYLOAD_START))

failures = 0

for name in ["T0_baseline", "C1_settle_dc_constant", "T1_blockwise_linear",
             "T2_exp_transient", "T3_hermite", "T4_kalman", "T5_kalman_crossframe"]:
    prior = None
    traj_a, st_a = TK.dc_trajectory(name, make_burst(payload_a), prior)
    traj_b, st_b = TK.dc_trajectory(name, make_burst(payload_b), prior)

    # finite
    ok = bool(np.all(np.isfinite(traj_a)))
    # correct length
    ok &= len(traj_a) == n
    # payload-independent: changing ONLY the payload must not move the trajectory
    ok &= np.array_equal(traj_a, traj_b)
    # bounded (no overshoot blow-up)
    ok &= float(np.max(np.abs(traj_a))) < 1e3

    # T0 must be identically zero; C1 must be the settle mean constant
    if name == "T0_baseline":
        ok &= bool(np.all(traj_a == 0.0))
    if name == "C1_settle_dc_constant":
        ok &= bool(np.all(traj_a == traj_a[0]))

    status = "OK " if ok else "FAIL"
    mx = float(np.max(np.abs(traj_a)))
    print("[%s] %-24s max|dc|=%.3f" % (status, name, mx))
    failures += 0 if ok else 1

print("smoke: %d failure(s)" % failures)
sys.exit(1 if failures else 0)
