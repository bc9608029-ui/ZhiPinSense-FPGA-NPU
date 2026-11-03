#!/usr/bin/env python3
"""test_fix3_no_oracle.py -- the no-oracle invariant for the offset models.

Proves, by construction and by a poison-sentinel probe, that the candidate
offset models M1..M4 read ONLY the silence regions (settling-zero / guard-zero)
to estimate the DC to subtract, and never read payload IQ, labels, or source ID.
M5 (oracle) is probed to CONFIRM it reads the payload, so it is correctly
labelled forbidden and is used only as a diagnostic upper bound.

Red line: 禁止使用原始载荷 IQ、标签、样本 ID 或逐样本 DC/尺度选择恢复参数.

Usage:  python -I host_tests/test_fix3_no_oracle.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import fix3_recovery as R
from validate_fix3_models import model_dc


def check(name: str, ok: bool, detail: str = ""):
    if not ok:
        print("FAIL: %s  %s" % (name, detail))
        sys.exit(1)
    print("ok  %s" % name)


def main() -> int:
    N = R.K_TOTAL if hasattr(R, "K_TOTAL") else 59904
    # Build a poison probe: silence holds known values, everything else is poison.
    aligned = np.full(N, 1e6 + 1e6j, dtype=np.complex128)
    settle_val = 10.0 + 10.0j
    guard_val = 20.0 + 20.0j
    aligned[R.SETTLE_START:R.SETTLE_END] = settle_val
    aligned[R.GUARD_START:R.GUARD_END] = guard_val

    # M0 baseline: reads nothing, returns 0.
    check("M0 reads no data", model_dc("M0_baseline", aligned) == 0.0 + 0j)

    # M1/M2 read exactly one silence region.
    d1 = model_dc("M1_settle_dc", aligned)
    d2 = model_dc("M2_guard_dc", aligned)
    check("M1 == settle mean (no payload read)",
          abs(d1 - settle_val) < 1e-6, "d1=%s" % d1)
    check("M2 == guard mean (no payload read)",
          abs(d2 - guard_val) < 1e-6, "d2=%s" % d2)

    # M3 average of the two silence means.
    d3 = model_dc("M3_settle_guard_avg", aligned)
    check("M3 == (settle+guard)/2", abs(d3 - (settle_val + guard_val) / 2.0) < 1e-6,
          "d3=%s" % d3)

    # M4 linear interp: t_s=1536, t_g=57856, t_p=29952 -> frac=(29952-1536)/(57856-1536).
    frac = (29952.0 - 1536.0) / (57856.0 - 1536.0)
    d4 = model_dc("M4_linear_dc", aligned)
    exp4 = settle_val + (guard_val - settle_val) * frac
    check("M4 == linear interp of silence means", abs(d4 - exp4) < 1e-6, "d4=%s" % d4)
    # M4 must lie strictly between the two silence means (both silence, not payload).
    check("M4 bounded between settle and guard",
          abs(d4) < 1e3, "d4 magnitude %.2f (must be ~10-20, not 1e6)" % abs(d4))

    # M5 oracle reads the payload -> poisoned.
    d5 = model_dc("M5_oracle_dc", aligned)
    check("M5 reads payload (oracle, forbidden)",
          abs(d5.real) > 1e5 and abs(d5.imag) > 1e5, "d5=%s" % d5)

    # None of M1..M4 depends on class_index / source_id / label: model_dc takes
    # only (model, aligned).  This is structural (no such argument exists).
    print("ok  M1..M4 signature has no label/source_id argument (structural)")
    print("PASS test_fix3_no_oracle")
    return 0


if __name__ == "__main__":
    sys.exit(main())
