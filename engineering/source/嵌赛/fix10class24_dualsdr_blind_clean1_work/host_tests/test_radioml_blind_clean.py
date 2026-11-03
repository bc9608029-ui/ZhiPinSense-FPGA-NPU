#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_radioml_blind_clean.py -- host tests for fix10class24-dualsdr-blind-clean1.

Runs the four self-tests (TX generation / PC TX service / digital replay / judger)
plus cross-module integration checks, all OFFLINE (no SDR, no RF, no icraft-run, no
board).  The model inference is NOT run here (that needs icraft-run.exe); the digital
replay's reconstruction/rotation logic is exercised instead.

Run (isolated, so no same-name module is picked up from CWD):
    python -I host_tests/test_radioml_blind_clean.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SCRIPTS = ROOT / "scripts"
HOST_TOOLS = ROOT / "host_tools"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(HOST_TOOLS))

import radioml_blind_clean_contract as BC        # noqa: E402
import pc_tx_blind_clean as PCTX                 # noqa: E402
import digital_replay_radioml_blind_clean as DR  # noqa: E402
import judge_radioml_blind_clean as JUDGE        # noqa: E402


def run_self_tests():
    results = []
    results.append(("tx generation self-test", BC.self_test()))
    results.append(("pc tx service self-test", PCTX.self_test()))
    results.append(("digital replay self-test", DR.self_test()))
    results.append(("judger self-test", JUDGE.self_test()))
    return results


def integration_checks():
    """Cross-module integration: package -> manifest -> replay -> judge."""
    ok = 0
    total = 0
    def check(name, cond):
        nonlocal ok, total
        total += 1
        if cond:
            ok += 1
        print("  %-56s %s" % (name, "PASS" if cond else "FAIL"))

    with tempfile.TemporaryDirectory() as td:
        tx = Path(td) / "tx"
        summary = BC.write_tx_package(tx)

        # package contents
        check("24 .i16 payloads written",
              sorted(int(f.stem) for f in tx.glob("*.i16")) == list(range(1, 25)))
        check("manifest 24 rows + header",
              len((tx / "blind_tx_manifest.tsv").read_text().splitlines()) == 25)
        check("SHA256SUMS sidecar present", (tx / "SHA256SUMS.txt").is_file())
        check("summary token", summary["token"] == BC.TOKEN)

        # manifest -> replay -> judge chain
        manifest = JUDGE.load_tx_manifest(tx)
        check("judge load_tx_manifest 24 rows", len(manifest) == 24)

        replay_rows = DR.load_tx_package(tx)
        check("replay load_tx_package 24 rows ordered", len(replay_rows) == 24
              and replay_rows[0]["source_index"] == 1
              and replay_rows[-1]["source_index"] == 24)

        # reconstruction: exact roundtrip must be ~ lossless
        wf = BC.GEN.generate_class("QPSK", BC.SEED_BASE + 4)
        ci16 = BC.quantize_ci16(wf, BC.TX_SCALE)
        z = DR.reconstruct_from_i16(ci16.tobytes())
        rel = float(np.sqrt(np.mean(np.abs(wf - z) ** 2)) /
                    np.sqrt(np.mean(np.abs(wf) ** 2)))
        check("quantization roundtrip rel RMS < 1e-2", rel < 1e-2)

        # source_index -> class is a bijection (blind ordinal, class not derivable)
        sids_to_class = {int(r["tx_payload_file"].split(".")[0]): r["class_index"]
                         for r in BC.build_all_waveforms()[0]}
        check("source_index->class bijection", sorted(sids_to_class) == list(range(1, 25))
              and sorted(sids_to_class.values()) == list(range(24)))

        # PC TX manifest agrees with the TX package (same SHA, same files)
        pctx_idx = PCTX.load_manifest(tx)
        check("PC TX manifest 24 entries", sorted(pctx_idx) == list(range(1, 25)))
        for s in range(1, 25):
            row = [r for r in replay_rows if r["source_index"] == s][0]
            if pctx_idx[s]["sha256"] != row["tx_payload_sha256"]:
                check("PC TX SHA agrees with manifest (source_index=%d)" % s, False)
                break
        else:
            check("PC TX SHA agrees with manifest (all 24)", True)

    return ok, total


def main() -> int:
    print("== self-tests ==")
    results = run_self_tests()
    print("== integration ==")
    iok, itotal = integration_checks()

    all_ok = all(r[1] == 0 for r in results) and iok == itotal
    n_ok = sum(1 for _, rc in results if rc == 0) + iok
    n_total = len(results) + itotal
    print("test_radioml_blind_clean: %d/%d PASS" % (n_ok, n_total))
    for name, rc in results:
        print("  self-test %-24s rc=%d" % (name, rc))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
