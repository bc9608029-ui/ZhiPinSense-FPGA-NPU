#!/usr/bin/env python3
"""test_fix3_r1_reestimate.py -- self-test the FIX3-REVIEW-R1 re-estimation logic.

Verifies, WITHOUT any Host inference:
  1. wide_linear_cond is correct and shows the matrix is WELL-conditioned
     (cond ~ 1.09 for the real RF a/b), so the "ill-conditioned / 1000x"
     narrative is retired in favor of "bias gain ~ 1/|a| ~ 32x".
  2. dc_samples: M0 zero; M1/M2/M3/M5 are CONSTANT; M4 is a true per-sample
     linear ramp anchored at the silence means.
  3. M1-M4 read ONLY the silence regions (perturbing the payload must not
     change the estimated DC).
  4. Re-estimation faithfulness: M0 baseline reproduces the board's
     residual_rel for a real frame (byte-faithful chain).

Usage: python -I host_tests/test_fix3_r1_reestimate.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

_SCRIPTS = str(Path(__file__).resolve().parent.parent / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import fix3_common as c
import fix3_recovery as R
import reestimate_fix3_r1 as RR

CAPTURE_DIR = Path(r"F:\嵌赛\board_capture\rml24_fix2_dual_1773374951_244")

checks: list[bool] = []


def check(name: str, ok: bool, detail: str = ""):
    checks.append(bool(ok))
    print("R1-SELFTEST %-58s %s%s" %
          (name, "PASS" if ok else "FAIL", (" -- " + detail) if detail else ""))


# 1. condition number ----------------------------------------------------------
cond_ident = RR.wide_linear_cond(1.0 + 0j, 0.0 + 0j)
check("cond identity channel == 1.0", abs(cond_ident - 1.0) < 1e-9,
      "cond=%.6f" % cond_ident)

a, b = 0.031 + 0j, 0.0014 + 0j
cond_rf = RR.wide_linear_cond(a, b)
# analytic: singular values are |a|+|b| and |a|-|b| for real a,b
cond_expect = (abs(a) + abs(b)) / (abs(a) - abs(b))
denom = abs(a) ** 2 - abs(b) ** 2
inv_gain = 1.0 / abs(a)
check("cond well-conditioned (not near-singular)", cond_rf < 1.2 and cond_rf > 1.0,
      "cond=%.4f (expect ~%.4f)" % (cond_rf, cond_expect))
check("denom small BECAUSE |a| small", denom < 1e-3 and abs(a) < 0.05,
      "denom=%.6f a=%.4f" % (denom, abs(a)))
check("bias gain is ~1/|a|, NOT 1/denom", inv_gain < 100.0,
      "1/|a|=%.1f vs 1/denom=%.0f (retired 1000x claim)" % (inv_gain, 1.0 / denom))

# 2. dc_samples: M4 is a per-sample ramp; M1/M2/M3/M5 are constant ------------
n = 59904  # K_TOTAL (full burst length) so the silence/payload slices are valid
raw = np.random.RandomState(0).randn(n) + 1j * np.random.RandomState(1).randn(n)
aligned = raw.copy()
timing = 0
for m in ["M1_settle_dc", "M2_guard_dc", "M3_settle_guard_avg", "M5_payload_mean_bound"]:
    dc = RR.dc_samples(m, raw, aligned, timing)
    check("%s is CONSTANT" % m, np.allclose(dc, dc[0]),
          "spread=%.2e" % float(np.max(np.abs(dc - dc[0]))))

dc4 = RR.dc_samples("M4_linear_drift", raw, aligned, timing)
# ramp: constant first-difference
d = np.diff(dc4)
check("M4 is a per-sample linear ramp (constant slope)",
      np.allclose(d, d[0], atol=1e-9),
      "slope spread=%.2e" % float(np.max(np.abs(d - d[0]))))
check("M4 ramp finite and non-trivial",
      bool(np.all(np.isfinite(dc4))) and bool(np.any(np.abs(dc4 - dc4[0]) > 0)),
      "all finite + slope!=0")

# 3. M1-M4 read only silence regions -----------------------------------------
# perturb the PAYLOAD region only; silence regions untouched
aligned2 = aligned.copy()
aligned2[R.PAYLOAD_START:R.PAYLOAD_END] += 500.0 + 300j
for m in ["M1_settle_dc", "M2_guard_dc", "M3_settle_guard_avg", "M4_linear_drift"]:
    dc_a = RR.dc_samples(m, raw, aligned, timing)
    dc_b = RR.dc_samples(m, raw, aligned2, timing)
    check("%s ignores payload (silence-only)" % m, np.allclose(dc_a, dc_b),
          "max|dDC|=%.2e" % float(np.max(np.abs(dc_a - dc_b))))

# 4. re-estimation faithfulness: M0 reproduces board residual for frame 1 -----
raw1, _ = R.load_burst(CAPTURE_DIR, 1)
est0 = R.estimate_public_reference_fix2(raw1)
check("frame1 M0 residual_rel matches board (0.0986)",
      abs(est0["training_residual_rel"] - 0.0986326207) < 1e-4,
      "rr=%.6f" % est0["training_residual_rel"])
# M0 dc == 0 => re-estimation identical to baseline
dc0 = RR.dc_samples("M0_baseline", raw1, R.aligned_burst(raw1, est0),
                    int(est0["timing_offset"]))
check("M0 dc == 0", np.all(dc0 == 0.0), "nonzero count=%d" % int(np.count_nonzero(dc0)))

all_ok = all(checks)
print("TEST_FIX3_R1_REESTIMATE %s (%d/%d)" %
      ("PASS" if all_ok else "FAIL", sum(checks), len(checks)))
sys.exit(0 if all_ok else 1)
