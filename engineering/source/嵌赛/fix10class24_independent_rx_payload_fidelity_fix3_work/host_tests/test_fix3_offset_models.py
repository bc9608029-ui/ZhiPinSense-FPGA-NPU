#!/usr/bin/env python3
"""test_fix3_offset_models.py -- pins the recovery substrate + offset-model deltas.

1. M0 baseline (recover_v2) reproduces the board's persisted recovered tensor
   SHA-256 for all 24 RF frames -- the byte-exact substrate every offset model
   is built on.  If this fails, nothing downstream is trustworthy.
2. Each offset model M1..M4 produces a tensor that (a) differs from M0 for at
   least one frame (i.e. the subtraction is not a silent no-op), and (b) stays
   finite with exactly 1024 complex samples.

Usage:  python -I host_tests/test_fix3_offset_models.py \
            --capture-dir F:/嵌赛/board_capture/rml24_fix2_dual_1773374951_244
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import fix3_common as c
import fix3_recovery as R
from validate_fix3_models import model_dc


def check(name: str, ok: bool, detail: str = ""):
    if not ok:
        print("FAIL: %s  %s" % (name, detail))
        sys.exit(1)
    print("ok  %s" % name)


def main(argv) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--capture-dir", required=True)
    args = ap.parse_args(argv)
    capture_dir = Path(args.capture_dir)

    results = c.load_results_tsv(capture_dir / "board_independent_rx_results.tsv")
    n = len(results)

    # 1. M0 byte-exact reproduction of the board tensors.
    agree = 0
    for r in results:
        sid = int(r["source_index"])
        rx_burst, _ = R.load_burst(capture_dir, sid)
        est = R.estimate_public_reference_fix2(rx_burst)
        rec = R.recover_v2(rx_burst, est)
        board_sha = r["model_input_sha256"]
        if c.sha256_bytes(R.tensor_to_bytes(rec)) == board_sha:
            agree += 1
    check("M0 reproduces board tensor SHA 24/24", agree == n, "%d/%d" % (agree, n))

    # 2. Offset models differ from M0 for at least one frame, and stay finite/1024.
    for m in ("M1_settle_dc", "M2_guard_dc", "M3_settle_guard_avg", "M4_linear_dc"):
        diffs = 0
        for r in results:
            sid = int(r["source_index"])
            rx_burst, _ = R.load_burst(capture_dir, sid)
            est = R.estimate_public_reference_fix2(rx_burst)
            aligned = R.aligned_burst(rx_burst, est)
            dc = model_dc(m, aligned)
            rec0 = R.recover_v2(rx_burst, est)
            rec1 = R.recover_v2_with_dc(rx_burst, est, dc)
            check("%s finite + 1024" % m,
                  rec1.size == R.MODEL_WINDOW and np.all(np.isfinite(rec1)))
            if not np.array_equal(rec0, rec1):
                diffs += 1
        check("%s changes at least one tensor vs M0" % m, diffs >= 1,
              "%d/%d differ" % (diffs, n))

    print("PASS test_fix3_offset_models")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
