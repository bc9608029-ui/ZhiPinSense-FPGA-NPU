#!/usr/bin/env python3
"""fix4_residual_ref.py -- corrected public-reference residual (Fix4 REVIEW-R1).

Fix4 R1 treated the received train/tail **block means** as DC observations.  That
is wrong: train (16QAM) and tail (ZC root-3) are KNOWN non-zero-mean sequences, so
a block mean conflates the known sequence's own mean with the LO DC.

Correct definition (REVIEW-R1, per the taskbook requirements 2/3/4/5):

    public_residual[n] = actual_received_public_block[n] - pred[n]

where pred[n] is the received public block predicted by the forward model

    pred[n] = ( a * frac_delay_sinc(x_ref, tau)[n]
              + b * conj(frac_delay_sinc(x_ref, tau)[n]) )
            * exp(+j * 2*pi * cfo * (n + start) / FS)

and x_ref is the FROZEN public reference:

    settle = zeros(1024)   (silence  -> reference is identically 0)
    guard  = zeros(2048)   (silence  -> reference is identically 0)
    train  = 16QAM training sequence  (real, non-zero mean -276-276j)
    tail   = ZC root-3 sequence       (real, non-zero mean -45-45j)

The per-sample residual is computed in the RAW (aligned) domain; the prediction
carries the CFO rotation (requirement 3's literal "经 timing/CFO/a/b/尺度模型预测").
Only AFTER this per-sample reference subtraction do we form sub-block residual
means (requirement 5).

The frozen references are the actual public sequences, NOT synthetic random
blocks (requirement 7).  Reads only public regions -- never the unknown payload.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_CONTRACT_DIR = r"F:\嵌赛\fix10class24_independent_rx_delivery_fix1_work\scripts"
_FIX3_DIR = r"F:\嵌赛\fix10class24_independent_rx_payload_fidelity_fix3_work\scripts"
_FIX2_DIR = r"F:\嵌赛\fix10class24_independent_rx_recovery_fix2_work\scripts"
for _p in (_CONTRACT_DIR, _FIX3_DIR, _FIX2_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import radioml_independent_rx_contract as IRX  # noqa: E402
import radioml_dualsdr_common as C             # noqa: E402
import radioml_dualsdr_burst as BURST          # noqa: E402
import fix3_recovery as R                      # noqa: E402
from reproduce_fix2_diagnosis import FS        # noqa: E402
from radioml_independent_rx_recovery_fix2 import frac_delay_sinc  # noqa: E402

PI = 3.141592653589793238462643383279502884

# Frozen public references (complex128), aligned coordinates.
PUBLIC_REFERENCE = {
    "settle": np.zeros(1024, dtype=np.complex128),          # silence
    "train": IRX.payload_training_complex(),                # 16QAM, amp 2896.309
    "guard": np.zeros(2048, dtype=np.complex128),           # silence
    "tail": C.deinterleave_int16(BURST.tail_int16()),       # ZC root-3, amp 2048
}

BLOCK_START = {
    "settle": R.SETTLE_START,   # 1024
    "train": R.TRAIN_START,     # 2048
    "guard": R.GUARD_START,     # 56832
    "tail": R.TAIL_START,       # 58880
}
BLOCK_LEN = {
    "settle": R.SETTLE_END - R.SETTLE_START,   # 1024
    "train": R.TRAIN_END - R.TRAIN_START,      # 1024
    "guard": R.GUARD_END - R.GUARD_START,      # 2048
    "tail": R.TAIL_END - R.TAIL_START,         # 1024
}
BLOCK_ORDER = ["settle", "train", "guard", "tail"]

SUB_LEN = 256   # frozen sub-block length for residual anchors (requirement 5)

# REVIEW-R1 复审 sensitivity knob: frac_delay_sinc uses circular indexing with
# half-length FRAC_DELAY_HALF=16, so the first/last 16 samples of each non-zero
# public block (train/tail) wrap around and can contaminate the edge sub-block
# residual anchors.  EDGE_TRIM excludes the first/last EDGE_TRIM samples of every
# public block before forming sub-block means.  0 = baseline (no trim); set via
# `reestimate_fix4_r1.py --edge-trim 16|32` for the sensitivity re-run.
EDGE_TRIM = 0


def reference_mean(block_name: str) -> complex:
    """The known public reference's own complex mean (non-zero for train/tail)."""
    return complex(np.mean(PUBLIC_REFERENCE[block_name]))


def predict_public_block(est: dict, block_name: str) -> np.ndarray:
    """Forward-model prediction of the received public block (aligned coords).

    pred[n] = (a*x_tau[n] + b*conj(x_tau[n])) * exp(+j*2*pi*cfo*(n+start)/FS),
    x_tau = frac_delay_sinc(x_ref, tau).  `a`/`b` absorb the TX->RX gain, so no
    separate scale term is needed (requirement 3's 尺度 is inside a/b).
    """
    ref = PUBLIC_REFERENCE[block_name]
    tau = est["fractional_timing"]
    x_tau = frac_delay_sinc(ref, tau)
    wl = est["a"] * x_tau + est["b"] * np.conj(x_tau)
    start = BLOCK_START[block_name]
    n = np.arange(len(ref), dtype=np.float64) + start
    ph = 2.0 * PI * est["coarse_cfo_hz"] * n / FS
    return wl * (np.cos(ph) + 1j * np.sin(ph))


def public_residual(aligned: np.ndarray, est: dict, block_name: str) -> np.ndarray:
    """Per-sample residual: actual received public block - predicted reference."""
    start = BLOCK_START[block_name]
    length = BLOCK_LEN[block_name]
    seg = aligned[start:start + length]
    return seg - predict_public_block(est, block_name)


def residual_anchors(aligned: np.ndarray, est: dict,
                     sub_len: int = SUB_LEN,
                     edge_trim: int | None = None) -> list[tuple[float, complex]]:
    """Sub-block residual means across all four public blocks (aligned coords).

    Per-sample reference subtraction happens FIRST (public_residual); only then is
    each contiguous sub-block's complex residual mean taken (requirement 5).
    Returns list of (center_time, complex residual mean), in block order.

    `edge_trim` excludes the first/last `edge_trim` samples of each public block
    before the sub-block division (frac_delay_sinc circular edge wrap); None uses
    the module-global EDGE_TRIM.
    """
    if edge_trim is None:
        edge_trim = EDGE_TRIM
    edge_trim = int(edge_trim)
    anchors: list[tuple[float, complex]] = []
    for name in BLOCK_ORDER:
        resid = public_residual(aligned, est, name)
        start = BLOCK_START[name]
        L = len(resid)
        lo0 = edge_trim
        hi0 = L - edge_trim
        if hi0 - lo0 < sub_len:          # degenerate: fall back to the full block
            lo0, hi0 = 0, L
        nsub = max(1, (hi0 - lo0) // sub_len)
        for k in range(nsub):
            lo = lo0 + k * sub_len
            hi = lo + sub_len
            center = start + (lo + hi) / 2.0
            anchors.append((center, complex(np.mean(resid[lo:hi]))))
    return anchors


def residual_anchor_magnitudes(aligned: np.ndarray, est: dict,
                               sub_len: int = SUB_LEN,
                               edge_trim: int | None = None) -> np.ndarray:
    """|residual anchor| array -- the corrected DC observability magnitude."""
    return np.array([abs(z) for _, z in
                     residual_anchors(aligned, est, sub_len, edge_trim)])


def self_test() -> int:
    checks: list[bool] = []

    def check(name, ok, detail=""):
        checks.append(bool(ok))
        print("FIX4-RESIDUAL-REF-SELFTEST %-58s %s%s" %
              (name, "PASS" if ok else "FAIL", (" -- " + detail) if detail else ""))

    # R1: the known public sequences have non-zero means (the crux of the review).
    m_tr = reference_mean("train")
    m_tl = reference_mean("tail")
    check("R1 train 16QAM reference mean is non-zero (|mean|>100)",
          abs(m_tr) > 100.0, "train mean=%.1f%+.1fj |mean|=%.1f"
          % (m_tr.real, m_tr.imag, abs(m_tr)))
    check("R1 tail ZC reference mean is non-zero (|mean|>10)",
          abs(m_tl) > 10.0, "tail mean=%.1f%+.1fj |mean|=%.1f"
          % (m_tl.real, m_tl.imag, abs(m_tl)))
    check("R1 settle/guard references are zero", abs(reference_mean("settle")) == 0.0
          and abs(reference_mean("guard")) == 0.0)

    # R2: in the digital (no-RF) domain, reference subtraction drives the residual
    #     to quantization error, NOT to the reference's own mean.
    max_anchor = 0.0
    for ci in range(IRX.N_CLASSES):
        wf = IRX.generate_waveform(ci)
        rx = C.deinterleave_int16(IRX.build_public_protocol_burst(wf))
        est = IRX.estimate_public_reference(rx)   # digital: a~1 b~0 cfo~0 tau~0
        # estimate_public_reference returns no 'fractional_timing'; use fix2 est.
        est2 = _fix2_est_for_digital(rx)
        mags = residual_anchor_magnitudes(rx, est2)
        max_anchor = max(max_anchor, float(mags.max()))
    check("R2 digital residual anchors ~ quantization error (max<20)", max_anchor < 20.0,
          "max_anchor=%.3f" % max_anchor)

    all_ok = all(checks)
    print("FIX4_RESIDUAL_REF_SELF_TEST %s (%d/%d)" %
          ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
    return 0 if all_ok else 1


def _fix2_est_for_digital(rx: np.ndarray) -> dict:
    from radioml_independent_rx_recovery_fix2 import estimate_public_reference_fix2
    return estimate_public_reference_fix2(rx)


if __name__ == "__main__":
    sys.exit(self_test())
