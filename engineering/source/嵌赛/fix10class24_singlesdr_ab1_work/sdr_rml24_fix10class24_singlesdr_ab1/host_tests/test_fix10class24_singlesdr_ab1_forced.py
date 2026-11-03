#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_fix10class24_singlesdr_ab1_forced.py -- host tests for the
fix10class24-singlesdr-ab1 four-metric aggregator + board script.

Loads the SAME aggregator the operator runs
(scripts/aggregate_fix10class24_singlesdr_ab1_forced.py) and statically inspects the
SAME board script (scripts/run_fix10class24_singlesdr_ab1.sh), so the tests exercise
the production four-metric merge + the single-SDR topology contract verbatim.  Pure
offline: no board, no libiio, no icraft-run, no model.
"""

import importlib.util
import os
import re
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, ".."))
_AGG_PATH = os.path.normpath(os.path.join(
    _ROOT, "scripts", "aggregate_fix10class24_singlesdr_ab1_forced.py"))
_BOARD_PATH = os.path.normpath(os.path.join(
    _ROOT, "scripts", "run_fix10class24_singlesdr_ab1.sh"))
_RUN_TESTS_PATH = os.path.normpath(os.path.join(_HERE, "run_tests.sh"))

_spec = importlib.util.spec_from_file_location("singlesdr_ab1_agg", _AGG_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load aggregator at %s" % _AGG_PATH)
agg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(agg)

with open(_BOARD_PATH, "r", encoding="utf-8") as _fh:
    BOARD = _fh.read()
with open(_RUN_TESTS_PATH, "r", encoding="utf-8") as _fh:
    RUN_TESTS = _fh.read()


def _mk_row(sid, sc, mod, valid, correct):
    return {
        "file_name": "clean_%s_%d.ci16" % (mod.lower(), sid),
        "source_index": sid, "raw24_class": sc, "modulation": mod,
        "snr_db": "18", "split_role": "holdout",
        "valid": valid, "raw24_pred": (sc if correct else (sc + 1) % 24),
        "baseline_pred": sc, "correct": correct,
        "prediction_agreement": correct, "repeat_deterministic": 1,
        "training_corr": "0.0", "training_residual": "0.0",
        "timing_offset": 0, "gain_mag": "0.0", "phase_deg": "0.0",
        "coarse_cfo_hz": "0.0", "fine_cfo_hz": "0.0", "total_cfo_hz": "0.0",
        "sro_ppm": "0.0", "rf_verdict": ("RF_PRESERVES_IQ" if valid else "RF_DISTORTS_IQ"),
    }


class TestFourMetricMerge(unittest.TestCase):
    def test_01_zero_refused(self):
        by = {i * 500: _mk_row(i * 500, i, "OOK", 1, i % 2 == 0) for i in range(24)}
        m = agg.compute_four_metrics(by, [], 24)
        self.assertEqual(m["scored"], 24)
        self.assertEqual(m["gated_correct"], 12)  # even i -> correct
        self.assertAlmostEqual(m["coverage"], 1.0)
        self.assertAlmostEqual(m["gated_accuracy"], 12 / 24)
        self.assertAlmostEqual(m["end_to_end_accuracy"], 12 / 24)
        self.assertAlmostEqual(m["forced_raw24_accuracy"], 12 / 24)

    def test_02_three_refused(self):
        by = {}
        for i in range(24):
            if i < 3:
                by[i * 500] = _mk_row(i * 500, i, "OOK", 0, -1)
            else:
                by[i * 500] = _mk_row(i * 500, i, "OOK", 1, i % 2 == 0)
        forced = [{"source_index": j * 500, "label_correct": 1 if j % 3 != 2 else 0}
                  for j in range(3)]
        m = agg.compute_four_metrics(by, forced, 24)
        self.assertEqual(m["scored"], 21)
        self.assertEqual(m["forced_count"], 3)
        self.assertEqual(m["forced_correct"], 2)  # j=0,1 correct; j=2 wrong
        gated_correct = sum(1 for i in range(3, 24) if i % 2 == 0)
        self.assertEqual(m["gated_correct"], gated_correct)
        self.assertAlmostEqual(m["coverage"], 21 / 24)
        self.assertAlmostEqual(m["forced_raw24_accuracy"], (gated_correct + 2) / 24)

    def test_03_twentyfour_refused(self):
        by = {i * 500: _mk_row(i * 500, i, "OOK", 0, -1) for i in range(24)}
        forced = [{"source_index": j * 500, "label_correct": 1 if j % 2 == 0 else 0}
                  for j in range(24)]
        m = agg.compute_four_metrics(by, forced, 24)
        self.assertEqual(m["scored"], 0)
        self.assertEqual(m["gated_accuracy"], 0.0)  # division-by-zero guard
        self.assertAlmostEqual(m["coverage"], 0.0)
        self.assertAlmostEqual(m["end_to_end_accuracy"], 0.0)
        self.assertAlmostEqual(m["forced_raw24_accuracy"], 12 / 24)

    def test_04_self_test_three_buckets(self):
        # The aggregator's own self-test must pass (proves no hardcoded 20/24).
        self.assertEqual(agg.self_test(), 0)


class TestBoardScriptTopology(unittest.TestCase):
    def test_05_single_sdr_no_tcp(self):
        self.assertIn("--phase=iq-rf-loopback-24class-bf16-fix10", BOARD)
        # Single-SDR: no PC TX, no TCP control channel anywhere.
        for banned in ("--tx-control", "tcp://", "39010", "PC_TX_IP",
                       "--pc-tx", "pc_tx_sdr", "TX_CONTROL"):
            self.assertNotIn(banned, BOARD)
        # Same URI drives TX and RX (no separate TX URI).
        self.assertIn("--rx-uri=\"$RX_URI\"", BOARD)
        self.assertNotIn("--tx-uri", BOARD)

    def test_06_rx_uri_required(self):
        self.assertIn('if [ -z "$RX_URI" ]', BOARD)
        self.assertIn("--rx-uri=<URI> is required", BOARD)
        self.assertIn("exit 2", BOARD)

    def test_07_mode_short2_full24(self):
        self.assertIn('MODE="full24"', BOARD)
        self.assertIn('--mode=*)', BOARD)
        self.assertIn("short2 or full24", BOARD)

    def test_08_bf16_model_not_23class_zg(self):
        # The board script MUST override the 23-class ZG default with the BF16 model.
        self.assertIn("MODEL_JSON=\"model_rml24_bf16/rml24_adamrv11_bf16.json\"", BOARD)
        self.assertIn("MODEL_RAW=\"model_rml24_bf16/rml24_adamrv11_bf16.raw\"", BOARD)
        self.assertNotIn("model_rml23", BOARD)
        self.assertNotIn("model_24class_ZG", BOARD)

    def test_09_tx_bw_and_safety_ceiling(self):
        self.assertIn("TX_BW=18000000", BOARD)
        self.assertIn('--tx-bw="$TX_BW"', BOARD)
        self.assertIn("TX_ATTEN=-40", BOARD)
        self.assertIn('--tx-atten="$TX_ATTEN"', BOARD)
        self.assertIn("--rf-path=direct-cable", BOARD)
        # No TX attenuation above the -40 dB ceiling anywhere.
        for bad in ("-35", "-30", "-25"):
            self.assertNotIn("TX_ATTEN=%s" % bad, BOARD)
            self.assertNotIn("--tx-atten %s" % bad, BOARD)

    def test_10_dump_flags_present(self):
        self.assertIn("--dump-failed-rx", BOARD)
        self.assertIn("--dump-recovery-diagnostics", BOARD)
        self.assertIn('--out-dir="$OUT_DIR"', BOARD)
        self.assertIn("tee \"$OUT_DIR/run.log\"", BOARD)

    def test_11_reports_pending_and_aggregator(self):
        self.assertIn("forced_raw24_accuracy=PENDING", BOARD)
        self.assertIn("aggregate_fix10class24_singlesdr_ab1_forced.py", BOARD)
        self.assertIn("HYBRID_BOARD_GATED_PLUS_HOST_FORCED", BOARD)


class TestWiring(unittest.TestCase):
    def test_12_new_test_wired_into_suite(self):
        self.assertIn("test_fix10class24_singlesdr_ab1_forced.py", RUN_TESTS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
