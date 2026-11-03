#!/usr/bin/env python3
"""REVIEW-R1 red-line test: corrected trackers are payload-blind.

The DC trajectory must be a pure function of the public reference blocks (via the
residual anchors) and the public-derived estimate; a payload carrying a huge
legitimate DC must not move the trajectory, and the trajectory must move when a
PUBLIC block changes.

Run:  python -I host_tests/test_fix4_r1_no_leak.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import fix4_common as FC       # noqa: E402
import trackers_fix4_r1 as TK  # noqa: E402

n = FC.K_TOTAL
PAY = FC.PAYLOAD_END - FC.PAYLOAD_START
failures = 0

# fixed public-derived estimate (public blocks only -> est is payload-blind).
EST = {"a": 1.0 + 0.0j, "b": 0.0 + 0.0j, "fractional_timing": 0.0,
       "coarse_cfo_hz": 0.0}


def make(payload):
    b = np.zeros(n, dtype=np.complex128)
    prng = np.random.default_rng(7)
    for a, bb in [(FC.SETTLE_START, FC.SETTLE_END), (FC.TRAIN_START, FC.TRAIN_END),
                  (FC.GUARD_START, FC.GUARD_END), (FC.TAIL_START, FC.TAIL_END)]:
        b[a:bb] = 0.01 * (prng.standard_normal(bb - a) + 1j * prng.standard_normal(bb - a))
    b[FC.PAYLOAD_START:FC.PAYLOAD_END] = payload
    return b


rng = np.random.default_rng(1)
noise = 0.01 * (rng.standard_normal(PAY) + 1j * rng.standard_normal(PAY))
legit_carrier = np.full(PAY, 100.0 + 50.0j)

for name in ["T1_blockwise_linear", "T2_exp_transient", "T3_hermite",
             "T4_kalman", "T5_kalman_crossframe"]:
    traj_legit, _ = TK.dc_trajectory(name, make(legit_carrier), EST, None)
    traj_noise, _ = TK.dc_trajectory(name, make(noise), EST, None)
    same = np.array_equal(traj_legit, traj_noise)
    ok = same and bool(np.all(np.isfinite(traj_legit)))
    print("[%s] %-24s legit-DC-carrier-invariant=%s" % ("OK " if ok else "FAIL", name, same))
    failures += 0 if ok else 1

# public-block sensitivity (not a no-op tracker).
b1, b2 = make(noise), make(noise)
b2[FC.SETTLE_START:FC.SETTLE_END] += 5.0 + 0.0j
t1, _ = TK.dc_trajectory("T1_blockwise_linear", b1, EST, None)
t2, _ = TK.dc_trajectory("T1_blockwise_linear", b2, EST, None)
sensitive = not np.array_equal(t1, t2)
print("[%s] public-block-sensitivity=%s" % ("OK " if sensitive else "FAIL", sensitive))
failures += 0 if sensitive else 1

print("no_leak_r1: %d failure(s)" % failures)
sys.exit(1 if failures else 0)
