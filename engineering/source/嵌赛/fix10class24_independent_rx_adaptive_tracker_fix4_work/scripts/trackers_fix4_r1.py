#!/usr/bin/env python3
"""trackers_fix4_r1.py -- corrected DC/LO trackers on residual anchors (REVIEW-R1).

Re-implements T0-T6 + the fix3-R1 C1 cross-check using the CORRECTED observable:
the sub-block residual means of `fix4_residual_ref.residual_anchors` (per-sample
reference subtraction first, then sub-block means), instead of R1's wrong
block-mean-as-DC.

Every tracker maps (aligned burst, est0) -> per-sample complex DC trajectory d[n]
in ALIGNED coordinates.  All trackers read ONLY the 4 public reference blocks via
the residual anchors; none read the unknown payload / class / label / logits.

The interpolators (_linear/_catmull_rom/_exp_transient/_constant_velocity) are
reused verbatim from the old trackers_fix4.py: they are pure "interpolate through
anchor points" math and do not contain the wrong block-mean definition.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fix4_residual_ref as RREF  # noqa: E402
from trackers_fix4 import (_linear, _catmull_rom, _exp_transient,  # noqa: E402
                           _constant_velocity, W_PRIOR)

TRACKERS = ["T0_baseline", "T1_blockwise_linear", "T2_exp_transient",
            "T3_hermite", "T4_kalman", "T5_kalman_crossframe", "T6_best_alternate"]
SELECTABLE = ["T1_blockwise_linear", "T2_exp_transient", "T3_hermite",
              "T4_kalman", "T5_kalman_crossframe"]


def _anchors(aligned: np.ndarray, est: dict):
    obs = RREF.residual_anchors(aligned, est, sub_len=RREF.SUB_LEN)
    ts = np.array([o[0] for o in obs], dtype=np.float64)
    zs = np.array([o[1] for o in obs], dtype=np.complex128)
    return ts, zs


def dc_trajectory(name: str, aligned: np.ndarray, est: dict, prior=None):
    """Return (dc_traj[n] complex, state_dict).  `est` is the frame's est0."""
    n = len(aligned)
    if name == "T0_baseline":
        return np.zeros(n, dtype=np.complex128), None
    if name == "C1_settle_dc_constant":   # fix3-R1 M1 anchor (cross-check only)
        # settle reference is 0 -> settle residual == received settle; its mean = DC.
        resid = RREF.public_residual(aligned, est, "settle")
        return np.full(n, complex(np.mean(resid)), dtype=np.complex128), None
    ts, zs = _anchors(aligned, est)
    if name == "T1_blockwise_linear":
        return _linear(ts, zs, n), None
    if name == "T2_exp_transient":
        return _exp_transient(ts, zs, n), None
    if name == "T3_hermite":
        return _catmull_rom(ts, zs, n), None
    if name == "T4_kalman":
        return _constant_velocity(ts, zs, n, prior=None)
    if name == "T5_kalman_crossframe":
        return _constant_velocity(ts, zs, n, prior=prior)
    raise ValueError("unknown tracker %s" % name)
