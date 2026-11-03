#!/usr/bin/env python3
"""trackers_fix4.py -- public-reference DC/LO drift trackers (T0-T6).

Every tracker maps a received burst to a per-sample complex DC trajectory d[n]
(59904 samples, ALIGNED coordinates).  All trackers read ONLY the 4 public
reference blocks (settle/train/guard/tail); none read the unknown payload, class,
label, or logits.  Category-independent; no per-class rules.

The trajectory is subtracted from the aligned burst BEFORE CFO removal / wide-linear
recovery (pointwise-linear, so it commutes with de-rotation).  The fix2 chain then
re-estimates timing/CFO/tau/a/b/residual on the DC-subtracted burst.

T0  baseline (no DC).
T1  block-wise linear interpolation through the 4 public DC observations.
T2  constant + exponential startup transient, tau selected by public-fit residual.
T3  cubic Hermite (Catmull-Rom) through the 4 observations (smooth C1).
T4  constant-velocity Kalman RTS smoother (update at observations, smooth across).
T5  cross-frame Kalman (T4 with prior state carried from the previous frame).
T6  best-of(T1..T5) by public training residual + alternating re-estimation
    (implemented in reestimate_fix4.py, not here).
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fix4_common as FC  # noqa: E402

TRACKERS = ["T0_baseline", "T1_blockwise_linear", "T2_exp_transient",
            "T3_hermite", "T4_kalman", "T5_kalman_crossframe", "T6_best_alternate"]
# T1..T5 are the model classes T6 selects from (T6 == alternating re-estimation).
SELECTABLE = ["T1_blockwise_linear", "T2_exp_transient", "T3_hermite",
              "T4_kalman", "T5_kalman_crossframe"]


# ---------------------------------------------------------------------------
# Interpolators (all category-independent; only the 4 public DC observations).
# ---------------------------------------------------------------------------
def _linear(ts, zs, n):
    xs = np.arange(n, dtype=np.float64)
    return (np.interp(xs, ts, zs.real) + 1j * np.interp(xs, ts, zs.imag))


def _catmull_rom(ts, zs, n):
    """Cubic Hermite (Catmull-Rom) through (ts, zs); one-sided end tangents."""
    ts = np.asarray(ts, dtype=np.float64)
    zs = np.asarray(zs, dtype=np.complex128)
    m = len(ts)
    d = np.empty(m, dtype=np.complex128)
    d[0] = (zs[1] - zs[0]) / (ts[1] - ts[0])
    d[-1] = (zs[-1] - zs[-2]) / (ts[-1] - ts[-2])
    for k in range(1, m - 1):
        d[k] = (zs[k + 1] - zs[k - 1]) / (ts[k + 1] - ts[k - 1])

    xs = np.arange(n, dtype=np.float64)
    out = np.zeros(n, dtype=np.complex128)
    for k in range(m - 1):
        t0, t1 = ts[k], ts[k + 1]
        p0, p1 = zs[k], zs[k + 1]
        m0, m1 = d[k], d[k + 1]
        h = t1 - t0
        sel = (xs >= t0) & (xs <= t1)
        if not np.any(sel):
            continue
        u = (xs[sel] - t0) / h
        u2, u3 = u * u, u * u * u
        h00 = 2 * u3 - 3 * u2 + 1
        h10 = u3 - 2 * u2 + u
        h01 = -2 * u3 + 3 * u2
        h11 = u3 - u2
        out[sel] = h00 * p0 + h10 * h * m0 + h01 * p1 + h11 * h * m1
    out[xs < ts[0]] = zs[0]
    out[xs > ts[-1]] = zs[-1]
    return out


def _exp_transient(ts, zs, n):
    """c + A*exp(-t/tau).  tau grid-selected by PUBLIC-observation fit residual."""
    ts = np.asarray(ts, dtype=np.float64)
    zs = np.asarray(zs, dtype=np.complex128)
    xs = np.arange(n, dtype=np.float64)
    taus = np.logspace(np.log10(256.0), np.log10(200000.0), 48)
    best = (np.inf, None)
    for tau in taus:
        B = np.column_stack([np.ones_like(ts), np.exp(-ts / tau)]).astype(np.complex128)
        coef, *_ = np.linalg.lstsq(B, zs, rcond=None)
        resid = float(np.sum(np.abs(B @ coef - zs) ** 2))
        if resid < best[0]:
            best = (resid, (tau, coef))
    tau, (c, A) = best[1]
    return c + A * np.exp(-xs / tau)


def _constant_velocity(ts, zs, n, prior):
    """Constant-velocity (dc + single rate) tracker = least-squares linear fit
    through the public DC observations.

    This is the stiff (q -> 0) limit of the 2-state dc+rate Gaussian smoother: a
    single global rate.  It is the only well-posed form here -- a global
    second-difference smoother with 4 widely-spaced scattered anchors is
    ill-conditioned (the linear-trend mode is nearly degenerate with the lowest
    curvature mode), so the finite-q MAP solve over-extrapolates.  The LS line is
    bounded, robust and is the exact constant-velocity estimate.

    prior=None => plain LS line.  prior != None (T5 cross-frame) => the line is
    additionally pinned near the settle centre to the previous frame's tail DC
    (the LO drift continues across back-to-back frames), with frozen weight.
    """
    ts = np.asarray(ts, dtype=np.float64)
    zs = np.asarray(zs, dtype=np.complex128)
    xs = np.arange(n, dtype=np.float64)

    if prior is None:
        A = np.column_stack([np.ones(len(ts)), ts])
        z = zs
        wts = np.ones(len(ts))
    else:
        t_settle = float(ts[0])
        A = np.column_stack([np.ones(len(ts) + 1),
                             np.append(ts, t_settle)])
        z = np.append(zs, complex(prior["dc_tail"]))
        wts = np.ones(len(ts) + 1)
        wts[-1] = W_PRIOR

    # weighted LS line y = a + b*t  (real and imag share the design matrix)
    W = np.diag(wts)
    Aw = W @ A
    coef_re, *_ = np.linalg.lstsq(Aw, wts * z.real, rcond=None)
    coef_im, *_ = np.linalg.lstsq(Aw, wts * z.imag, rcond=None)
    traj = (coef_re[0] + coef_re[1] * xs) + 1j * (coef_im[0] + coef_im[1] * xs)
    state = {"dc_tail": complex(traj[-1]),
             "rate_tail": complex(coef_re[1], coef_im[1])}
    return traj, state


W_PRIOR = 1.0   # frozen cross-frame prior weight (== one block-mean observation)


# ---------------------------------------------------------------------------
# Trajectory dispatch.
# ---------------------------------------------------------------------------
def dc_trajectory(name: str, aligned, prior=None):
    """Return (dc_traj[n] complex, state_dict)."""
    n = len(aligned)
    if name == "T0_baseline":
        return np.zeros(n, dtype=np.complex128), None
    if name == "C1_settle_dc_constant":   # fix3-r1 M1 anchor (cross-check only)
        return np.full(n, complex(aligned[FC.SETTLE_START:FC.SETTLE_END].mean()),
                       dtype=np.complex128), None
    obs = FC.public_dc_observations(aligned)
    ts = np.array([o[0] for o in obs], dtype=np.float64)
    zs = np.array([o[1] for o in obs], dtype=np.complex128)
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
