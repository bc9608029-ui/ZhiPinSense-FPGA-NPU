#!/usr/bin/env python3
"""REVIEW-R1 crux test: the known public sequences have non-zero means, so R1's
block-mean-as-DC leaked the reference's own mean; the corrected per-sample
residual does not.

Three assertions:
  (a) train(16QAM)/tail(ZC) reference means are non-zero (large);
  (b) the OLD block-mean-as-DC observation on a MATCHED received burst (received
      == reference, no RF, no DC) would report ~ the reference mean (a leak);
  (c) the CORRECTED residual anchor on the same matched burst is ~ 0.

Run:  python -I host_tests/test_fix4_r1_reference_means.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS))
import fix4_residual_ref as RREF  # noqa: E402
import fix3_recovery as R          # noqa: E402

failures = 0


def check(name, ok, detail=""):
    global failures
    failures += 0 if ok else 1
    print("[%s] %-56s %s" % ("OK " if ok else "FAIL", name, detail))


# (a) non-zero reference means.
m_tr = RREF.reference_mean("train")
m_tl = RREF.reference_mean("tail")
check("(a) train reference mean non-zero", abs(m_tr) > 100.0,
      "train mean=%.1f%+.1fj |mean|=%.1f" % (m_tr.real, m_tr.imag, abs(m_tr)))
check("(a) tail reference mean non-zero", abs(m_tl) > 10.0,
      "tail mean=%.1f%+.1fj |mean|=%.1f" % (m_tl.real, m_tl.imag, abs(m_tl)))

# Build a MATCHED received burst: received == frozen reference, no RF, no DC.
aligned = np.zeros(R.K_TOTAL, dtype=np.complex128)
for name in RREF.BLOCK_ORDER:
    s = RREF.BLOCK_START[name]
    aligned[s:s + RREF.BLOCK_LEN[name]] = RREF.PUBLIC_REFERENCE[name]

est = {"a": 1.0 + 0.0j, "b": 0.0 + 0.0j, "fractional_timing": 0.0,
       "coarse_cfo_hz": 0.0}

# (b) old block-mean-as-DC leaks the reference mean.
old_train_block_mean = complex(aligned[R.TRAIN_START:R.TRAIN_END].mean())
check("(b) OLD block-mean-as-DC leaks train reference mean (|blockmean| > 100)",
      abs(old_train_block_mean) > 100.0,
      "old block mean=%.1f%+.1fj (= reference mean, a leak)" %
      (old_train_block_mean.real, old_train_block_mean.imag))

# (c) corrected residual anchors ~ 0 on the matched burst.
mags = RREF.residual_anchor_magnitudes(aligned, est, sub_len=RREF.SUB_LEN)
check("(c) corrected residual anchors ~ 0 on matched burst (max < 1e-6)",
      float(mags.max()) < 1e-6, "max residual anchor=%.3e" % float(mags.max()))

print("reference_means: %d failure(s)" % failures)
sys.exit(1 if failures else 0)
