#!/usr/bin/env python3
"""test_fix3_interpolation_boundaries.py -- M4 linear-DC model boundary sanity.

M4 fits a linear ramp to the two silence-region means and evaluates it at the
payload midpoint.  This test pins, in isolation (synthetic aligned buffers, no
capture data), that:
  1. the anchor positions are the burst-layout midpoints (settle 1536, guard 57856);
  2. the payload-midpoint evaluation lies strictly within the convex hull of the
     two silence means (no extrapolation blow-up);
  3. the degenerate settle==guard case returns that exact value;
  4. the fraction is bounded in (0,1) given the anchor geometry.

Usage:  python -I host_tests/test_fix3_interpolation_boundaries.py
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


def make_aligned(settle: complex, guard: complex) -> np.ndarray:
    total = 59904  # K_TOTAL_BURST_COMPLEX
    a = np.zeros(total, dtype=np.complex128)
    a[R.SETTLE_START:R.SETTLE_END] = settle
    a[R.GUARD_START:R.GUARD_END] = guard
    return a


def main() -> int:
    # 1. anchor geometry (burst layout midpoints).
    t_s = (R.SETTLE_START + R.SETTLE_END) / 2.0
    t_g = (R.GUARD_START + R.GUARD_END) / 2.0
    t_p = (R.PAYLOAD_START + R.PAYLOAD_END) / 2.0
    check("settle anchor == 1536", t_s == 1536.0, "t_s=%.1f" % t_s)
    check("guard anchor == 57856", t_g == 57856.0, "t_g=%.1f" % t_g)
    frac = (t_p - t_s) / (t_g - t_s)
    check("payload midpoint fraction in (0,1)", 0.0 < frac < 1.0,
          "frac=%.4f" % frac)

    # 2. linear interp bounded within convex hull.
    cases = [
        (10.0 + 10.0j, 30.0 + 30.0j),
        (0.0 + 0.0j, 100.0 + 0.0j),
        (-8.0 + 5.0j, 6.0 - 4.0j),
    ]
    for settle, guard in cases:
        d = model_dc("M4_linear_dc", make_aligned(settle, guard))
        lo = min(settle.real, guard.real)
        hi = max(settle.real, guard.real)
        check("M4 real in [%.1f, %.1f]" % (lo, hi), lo - 1e-6 <= d.real <= hi + 1e-6,
              "d=%s" % d)
        lo_i = min(settle.imag, guard.imag)
        hi_i = max(settle.imag, guard.imag)
        check("M4 imag in [%.1f, %.1f]" % (lo_i, hi_i),
              lo_i - 1e-6 <= d.imag <= hi_i + 1e-6, "d=%s" % d)

    # 3. degenerate settle==guard.
    d = model_dc("M4_linear_dc", make_aligned(15.0 + 15.0j, 15.0 + 15.0j))
    check("M4 degenerate settle==guard returns exact value",
          abs(d - (15.0 + 15.0j)) < 1e-6, "d=%s" % d)

    print("PASS test_fix3_interpolation_boundaries")
    return 0


if __name__ == "__main__":
    sys.exit(main())
