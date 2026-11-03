#!/usr/bin/env python3
"""M0 byte-level reproduction: the T0 (no-DC) recovery must byte-match the
board-captured reference tensor, proving the Fix4 substrate is byte-exact with
the frozen fix2 recovery chain.

Run:  python -I host_tests/test_m0_byterepro.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

FIX3 = Path(r"F:\嵌赛\fix10class24_independent_rx_payload_fidelity_fix3_work\scripts")
sys.path.insert(0, str(FIX3))
import fix3_recovery as R  # noqa: E402

CAP = Path(r"F:\嵌赛\board_capture\rml24_fix2_dual_1773374951_244")
failures = 0

for sid in [1, 2, 3]:
    raw, _ = R.load_burst(CAP, sid)
    est0 = R.estimate_public_reference_fix2(raw)
    rec = R.recover_v2(raw, est0)          # T0 == est0 (no DC subtraction)
    x = np.empty((2, len(rec)), dtype="<f4")
    x[0] = rec.real.astype("<f4")
    x[1] = rec.imag.astype("<f4")
    ref = (CAP / ("%d.recovered.tensor.bin" % sid)).read_bytes()
    ok = ref == x.tobytes()
    print("[%s] sid=%d M0 byte-repro (%d bytes)" % ("OK " if ok else "FAIL", sid, len(ref)))
    failures += 0 if ok else 1

print("m0_byterepro: %d failure(s)" % failures)
sys.exit(1 if failures else 0)
