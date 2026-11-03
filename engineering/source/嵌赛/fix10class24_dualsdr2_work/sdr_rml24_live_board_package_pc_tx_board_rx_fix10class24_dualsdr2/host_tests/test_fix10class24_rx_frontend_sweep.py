#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_fix10class24_rx_frontend_sweep.py -- 12 host tests (§十一) for the
fix10class24-rxfrontend1 RX-bandwidth sweep tools.

Loads the SAME checker module the operator runs
(scripts/check_fix10class24_rx_frontend_sweep.py) and statically inspects the SAME
sweep script (scripts/run_fix10class24_rx_frontend_sweep.sh), so the tests exercise
the production parsing/judging logic verbatim.  Pure stdlib; no board, no libiio.
"""

import importlib.util
import os
import re
import shutil
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, ".."))
_CHECKER_PATH = os.path.normpath(os.path.join(
    _ROOT, "scripts", "check_fix10class24_rx_frontend_sweep.py"))
_SWEEP_PATH = os.path.normpath(os.path.join(
    _ROOT, "scripts", "run_fix10class24_rx_frontend_sweep.sh"))
_RUN_TESTS_PATH = os.path.normpath(os.path.join(_HERE, "run_tests.sh"))

_spec = importlib.util.spec_from_file_location("rxfrontend_checker", _CHECKER_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load checker at %s" % _CHECKER_PATH)
chk = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(chk)

with open(_SWEEP_PATH, "r", encoding="utf-8") as _fh:
    SWEEP_SCRIPT = _fh.read()
with open(_RUN_TESTS_PATH, "r", encoding="utf-8") as _fh:
    RUN_TESTS = _fh.read()


def make_log_text(bandwidth_hz=18000000, requested_rx_bw=None, rx_bw_readback=None,
                  rx_bw_ok=1, requested_rx_gain=35.0, rx_gain_readback=35.0,
                  rx_gain_ok=1, tx_atten_db=-40.0, bpsk_residual=0.05,
                  ask_residual=0.05, bpsk_clipped=0, ask_clipped=0,
                  bpsk_index=1500, ask_index=500, scored=2, rf_excluded=0,
                  nan_or_inf=0, negative_control="PASS", cfo_finite=1,
                  cfo_in_range=1, tx_restore=1, rx_restore=1,
                  prediction_agreement="2/2", label_correct="2/2",
                  repeat_deterministic="2/2", training_estimate_valid="2/2",
                  finite=1):
    if requested_rx_bw is None:
        requested_rx_bw = bandwidth_hz
    if rx_bw_readback is None:
        rx_bw_readback = requested_rx_bw

    def cfo_line(fname, mod):
        return ("FIX10CLASS24_BF16_CFO file=%s coarse_cfo_search_min_hz=-625.000 "
                "coarse_cfo_search_max_hz=625.000 coarse_cfo_unambiguous_range_hz=625.000 "
                "fine_cfo_range_hz=625.000 coarse_cfo_hz=-118.325 fine_cfo_hz=-6.265 "
                "total_cfo_hz=-124.590 fractional_timing_samples=0.294922 "
                "fractional_corr_before=0.990000 fractional_corr_after=0.993000 "
                "cfo_finite=%d cfo_in_range=%d" % (fname, cfo_finite, cfo_in_range))

    def recovery_line(fname, mod):
        resid = bpsk_residual if mod == "BPSK" else ask_residual
        clipped = bpsk_clipped if mod == "BPSK" else ask_clipped
        return ("FIX10CLASS24_BF16_RECOVERY file=%s computed=1 valid=1 "
                "failure=NONE timing=36074 gain_mag=0.015481 phase_deg=-3.317 "
                "fine_cfo_hz=-6.265 sro_ppm=0.000000 training_corr=0.990000 "
                "training_residual=0.010000 payload_gain_mag=0.015481 "
                "payload_rms_gain_mag=0.015481 payload_phase_deg=-3.317 "
                "payload_training_corr=0.993317 payload_training_residual=%.6f "
                "fidelity=RF_PRESERVES_IQ rx_clipped=%d" % (fname, resid, clipped))

    def classify_line(fname, mod):
        return ("FIX10CLASS24_BF16_CLASSIFY file=%s baseline_pred=3 rf_pred=3 "
                "source_label=3 prediction_agreement=1 label_correct=1 "
                "repeat_deterministic=1 finite=%d" % (fname, finite))

    lines = [
        "FIX10CLASS24_BF16_RX_FRONTEND requested_rx_bw=%d rx_bw_readback=%d "
        "requested_rx_gain=%.3f rx_gain_readback=%.3f rx_bw_ok=%d rx_gain_ok=%d"
        % (requested_rx_bw, rx_bw_readback, requested_rx_gain, rx_gain_readback,
           rx_bw_ok, rx_gain_ok),
        "FIX10CLASS24_BF16_HELLO_ACK tx_serial=1044f2deadbeef tx_uri=usb:1.11.5 "
        "tx_atten_db=%.3f configuration_verified=1" % tx_atten_db,
        "FIX10CLASS24_BF16_FILE file=clean_bpsk_4713bc2e.ci16 input_kind=radioml-d2-2p56m "
        "source_index=%d source_class=3 modulation=BPSK frozen_complex=53760 "
        "split_role=holdout" % bpsk_index,
        "FIX10CLASS24_BF16_FILE file=clean_4ask_a413e2d4.ci16 input_kind=radioml-d2-2p56m "
        "source_index=%d source_class=1 modulation=4ASK frozen_complex=53760 "
        "split_role=holdout" % ask_index,
        cfo_line("clean_bpsk_4713bc2e.ci16", "BPSK"),
        cfo_line("clean_4ask_a413e2d4.ci16", "4ASK"),
        recovery_line("clean_bpsk_4713bc2e.ci16", "BPSK"),
        recovery_line("clean_4ask_a413e2d4.ci16", "4ASK"),
        classify_line("clean_bpsk_4713bc2e.ci16", "BPSK"),
        classify_line("clean_4ask_a413e2d4.ci16", "4ASK"),
        "FIX10CLASS24_BF16_TWO_SAMPLE_RESULT scored=%d rf_excluded=%d "
        "prediction_agreement=%s label_correct=%s wc=0/0 sc=0/0 nan_or_inf=%d "
        "repeat_deterministic=%s tx_restore_ok=%d rx_restore_ok=%d "
        "negative_control=%s cfo_finite=%d cfo_in_range=%d "
        "training_estimate_valid=%s"
        % (scored, rf_excluded, prediction_agreement, label_correct, nan_or_inf,
           repeat_deterministic, tx_restore, rx_restore, negative_control,
           cfo_finite, cfo_in_range, training_estimate_valid),
    ]
    return "\n".join(lines) + "\n"


class TestSweepLevels(unittest.TestCase):
    def test_01_sweep_strictly_18_10_5_3(self):
        self.assertEqual(tuple(chk.BANDWIDTH_LEVELS_HZ),
                         (18000000, 10000000, 5000000, 3000000))
        self.assertEqual(chk.ROUNDS, 3)
        # The board script's level list must be exactly those four, in that order.
        m = re.search(r"BANDWIDTHS_HZ=\(([^)]*)\)", SWEEP_SCRIPT)
        self.assertIsNotNone(m)
        self.assertEqual(m.group(1).split(),
                         ["18000000", "10000000", "5000000", "3000000"])


class TestTxAttenCeiling(unittest.TestCase):
    def test_02_tx_atten_always_minus40(self):
        # The PC command embedded in the sweep script is the ONLY TX-atten statement,
        # and it is the -40 dB ceiling.
        self.assertIn("--tx-atten -40", SWEEP_SCRIPT)
        for bad in ("--tx-atten -35", "--tx-atten -30", "--tx-atten=-35",
                    "--tx-atten=-30"):
            self.assertNotIn(bad, SWEEP_SCRIPT)
        # The checker rejects any non-ceiling attenuation.
        rl = chk.parse_log_text(make_log_text(tx_atten_db=-35.0))
        ok, checks = chk.judge_round(rl, 18000000)
        self.assertFalse(ok)
        self.assertIn("tx_atten_is_ceiling=FAIL", checks)


class TestRxGainFixed(unittest.TestCase):
    def test_03_rx_gain_always_35(self):
        self.assertEqual(chk.RX_GAIN_DB_REQUIRED, 35.0)
        self.assertIn("RX_GAIN_DB=35", SWEEP_SCRIPT)
        for rl, ok in [(chk.parse_log_text(make_log_text(requested_rx_gain=35.0,
                                                         rx_gain_readback=35.0)),
                        True),
                       (chk.parse_log_text(make_log_text(requested_rx_gain=30.0,
                                                         rx_gain_readback=30.0)),
                        False),
                       (chk.parse_log_text(make_log_text(requested_rx_gain=40.0,
                                                         rx_gain_readback=40.0)),
                        False)]:
            got, checks = chk.judge_round(rl, 18000000)
            self.assertEqual(got, ok, msg=checks)


class TestOnlyRxBwVaries(unittest.TestCase):
    def test_04_all_params_verbatim_except_rx_bw(self):
        # In run_round(), every board parameter is fixed; only --rx-bw is driven by
        # the sweep loop variable $hz.
        self.assertIn('--rx-bw="$hz"', SWEEP_SCRIPT)
        self.assertIn('--rx-gain="$RX_GAIN_DB"', SWEEP_SCRIPT)
        self.assertIn('--center="$CENTER_HZ"', SWEEP_SCRIPT)
        self.assertIn('--rf-tx-target-rms=2048', SWEEP_SCRIPT)
        self.assertIn('--rf-path=direct-cable', SWEEP_SCRIPT)
        self.assertIn('--diagnostic-classes="$DIAGNOSTIC_CLASSES"', SWEEP_SCRIPT)
        # No other board parameter must be "$hz"-driven.
        driven = re.findall(r'(--[a-z0-9-]+)="\$hz"', SWEEP_SCRIPT)
        self.assertEqual(set(driven), {"--rx-bw"})


class TestCandidateRequiresThreeOfThree(unittest.TestCase):
    def test_05_three_of_three_required(self):
        # A full 3/3 is a candidate; 2/3 is not.
        full = {"bandwidth_hz": 18000000, "pass_rounds": 3, "total_rounds": 3}
        self.assertEqual(chk.select_candidate([full])["bandwidth_hz"], 18000000)
        two_of_three = {"bandwidth_hz": 10000000, "pass_rounds": 2, "total_rounds": 3}
        self.assertIsNone(chk.select_candidate([two_of_three]))

    def test_06_two_pass_one_fail_not_qualified(self):
        # A bandwidth with 2/3 rounds passing is NOT selected, even if nothing else
        # passed, so the verdict is NO_STABLE_RX_BANDWIDTH.
        only = {"bandwidth_hz": 18000000, "pass_rounds": 2, "total_rounds": 3}
        self.assertIsNone(chk.select_candidate([only]))


class TestResidualBoundary(unittest.TestCase):
    def test_07_residual_boundary(self):
        for resid, expected in [(0.100000, True), (0.099999, True), (0.100001, False),
                                (0.116199, False)]:
            rl = chk.parse_log_text(make_log_text(bpsk_residual=resid,
                                                  ask_residual=0.05))
            ok, checks = chk.judge_round(rl, 18000000)
            self.assertEqual(ok, expected,
                             msg="residual=%r -> %r (%s)" % (resid, ok, checks))


class TestHardFailures(unittest.TestCase):
    def test_08_clipping_nan_readback_mismatch_fail(self):
        # RX clipping fails the round.
        rl = chk.parse_log_text(make_log_text(bpsk_clipped=1))
        self.assertFalse(chk.judge_round(rl, 18000000)[0])
        # A NaN residual fails (never passes the <=0.10 comparison).
        rl = chk.parse_log_text(make_log_text(bpsk_residual=float("nan")))
        self.assertFalse(chk.judge_round(rl, 18000000)[0])
        # A bandwidth readback mismatch (rx_bw_ok=0) fails the round.
        rl = chk.parse_log_text(make_log_text(requested_rx_bw=18000000,
                                              rx_bw_readback=5000000, rx_bw_ok=0))
        self.assertFalse(chk.judge_round(rl, 18000000)[0])


class TestStructuralFailClosed(unittest.TestCase):
    def test_09_missing_log_duplicate_sample_wrong_index(self):
        # Missing run.log -> CheckError (not a silent pass).
        tmp = tempfile.mkdtemp(prefix="rxfrontend_test_")
        try:
            d = os.path.join(tmp, "rml24_rxbw_18000000_run1_12345")
            os.mkdir(d)
            for r in (2, 3):
                rd = os.path.join(tmp, "rml24_rxbw_18000000_run%d_12345" % r)
                os.mkdir(rd)
                with open(os.path.join(rd, "run.log"), "w") as fh:
                    fh.write(make_log_text(bandwidth_hz=18000000))
            with self.assertRaises(chk.CheckError):
                chk.analyze_bandwidth(tmp, 18000000)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

        # Duplicate modulation -> CheckError.
        dup = make_log_text() + ("FIX10CLASS24_BF16_FILE file=other.ci16 "
                                 "input_kind=radioml-d2-2p56m source_index=999 "
                                 "source_class=3 modulation=BPSK frozen_complex=53760 "
                                 "split_role=holdout\n")
        with self.assertRaises(chk.CheckError):
            chk.parse_log_text(dup)

        # Wrong source_index -> the identity check fails the round.
        rl = chk.parse_log_text(make_log_text(bpsk_index=999))
        ok, checks = chk.judge_round(rl, 18000000)
        self.assertFalse(ok)
        self.assertIn("bpsk_source_index=FAIL", checks)


class TestWidestCandidate(unittest.TestCase):
    def test_10_choose_widest_passing(self):
        s18 = {"bandwidth_hz": 18000000, "pass_rounds": 3, "total_rounds": 3}
        s10 = {"bandwidth_hz": 10000000, "pass_rounds": 3, "total_rounds": 3}
        s5 = {"bandwidth_hz": 5000000, "pass_rounds": 3, "total_rounds": 3}
        # Given 18/10/5 all pass, the widest (18 MHz) must win.
        self.assertEqual(chk.select_candidate([s5, s10, s18])["bandwidth_hz"], 18000000)
        # Given only 10 and 5 pass (18 failed), 10 MHz must win (widest of the passers).
        self.assertEqual(chk.select_candidate([s5, s10])["bandwidth_hz"], 10000000)


class TestNoStableBandwidth(unittest.TestCase):
    def test_11_no_candidate_is_no_stable(self):
        fails = [{"bandwidth_hz": hz, "pass_rounds": 0, "total_rounds": 3}
                 for hz in chk.BANDWIDTH_LEVELS_HZ]
        self.assertIsNone(chk.select_candidate(fails))


class TestFullSuiteWiring(unittest.TestCase):
    def test_12_new_test_wired_into_full_suite(self):
        self.assertIn("test_fix10class24_rx_frontend_sweep.py", RUN_TESTS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
