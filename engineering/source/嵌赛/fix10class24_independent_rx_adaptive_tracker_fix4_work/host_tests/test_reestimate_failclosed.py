#!/usr/bin/env python3
"""Fail-closed substrate tests: missing file / duplicate ID / malformed TSV /
NaN public block must all fail, not silently pass.

Run:  python -I host_tests/test_reestimate_failclosed.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import numpy as np

FIX3 = Path(r"F:\嵌赛\fix10class24_independent_rx_payload_fidelity_fix3_work\scripts")
SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(FIX3))
sys.path.insert(0, str(SCRIPTS))

import fix3_common as FC  # noqa: E402
import fix3_recovery as R  # noqa: E402
import fix4_common as FC4  # noqa: E402

CAP = Path(r"F:\嵌赛\board_capture\rml24_fix2_dual_1773374951_244")
failures = 0


def expect_fail(label, fn):
    global failures
    try:
        fn()
        ok = False
    except (SystemExit, FileNotFoundError, RuntimeError):
        ok = True
    print("[%s] %s" % ("OK " if ok else "FAIL", label))
    failures += 0 if ok else 1


# 1. missing burst file
expect_fail("load_burst missing sid",
            lambda: R.load_burst(Path(r"Z:\nonexistent_dir"), 999))

# 2. duplicate source_index in a results TSV (must fail-closed)
tmp = Path(tempfile.mkdtemp())
src_lines = (CAP / "board_independent_rx_results.tsv").read_text(encoding="utf-8").splitlines()
dup = tmp / "board_independent_rx_results.tsv"
dup.write_text("\n".join([src_lines[0], src_lines[1], src_lines[1]]) + "\n", encoding="utf-8")
expect_fail("load_results_tsv duplicate id", lambda: FC.load_results_tsv(dup))

# 3. malformed TSV row (wrong column count)
bad = tmp / "bad.tsv"
bad.write_text("a\tb\n1\t2\t3\n", encoding="utf-8")
expect_fail("read_tsv malformed row", lambda: FC.read_tsv(bad))

# 4. NaN in a public block must be observable (so the pipeline can reject it)
aligned = np.zeros(FC4.K_TOTAL, dtype=np.complex128)
aligned[FC4.SETTLE_START] = np.nan
obs = FC4.public_dc_observations(aligned)
nan_detect = any(not np.isfinite(o[1]) for o in obs)
print("[%s] NaN public block detected" % ("OK " if nan_detect else "FAIL"))
failures += 0 if nan_detect else 1

print("failclosed: %d failure(s)" % failures)
sys.exit(1 if failures else 0)
