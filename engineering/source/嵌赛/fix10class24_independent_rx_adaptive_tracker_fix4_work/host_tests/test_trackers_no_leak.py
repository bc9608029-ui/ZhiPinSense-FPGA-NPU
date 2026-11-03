#!/usr/bin/env python3
"""Red-line test: trackers are label/logits-blind and never touch a legitimate
payload DC carrier.

The DC trajectory must be a pure function of the 4 public reference blocks.  A
payload carrying a huge legitimate DC (e.g. an AM-SSB-WC-style carrier) must not
move the trajectory; and the trajectory must move when a PUBLIC block changes.

Run:  python -I host_tests/test_trackers_no_leak.py
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
PAY = FC.PAYLOAD_END - FC.PAYLOAD_START
failures = 0


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
legit_carrier = np.full(PAY, 100.0 + 50.0j)   # fake legitimate DC-carrier payload

for name in ["T1_blockwise_linear", "T2_exp_transient", "T3_hermite",
             "T4_kalman", "T5_kalman_crossframe"]:
    traj_legit, _ = TK.dc_trajectory(name, make(legit_carrier), None)
    traj_noise, _ = TK.dc_trajectory(name, make(noise), None)
    same = np.array_equal(traj_legit, traj_noise)
    ok = same and bool(np.all(np.isfinite(traj_legit)))
    print("[%s] %-24s legit-DC-carrier-invariant=%s" % ("OK " if ok else "FAIL", name, same))
    failures += 0 if ok else 1

# sanity: changing a PUBLIC block must move the trajectory (not a no-op tracker).
b1, b2 = make(noise), make(noise)
b2[FC.SETTLE_START:FC.SETTLE_END] += 5.0 + 0.0j
t1, _ = TK.dc_trajectory("T1_blockwise_linear", b1, None)
t2, _ = TK.dc_trajectory("T1_blockwise_linear", b2, None)
sensitive = not np.array_equal(t1, t2)
print("[%s] public-block-sensitivity=%s" % ("OK " if sensitive else "FAIL", sensitive))
failures += 0 if sensitive else 1

print("no-leak: %d failure(s)" % failures)
sys.exit(1 if failures else 0)
