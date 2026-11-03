#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_fix10class24_tx_rms_sweep1.py -- host tests for the fix10class24-tx-rms-sweep1
orchestration + audit tools.

Loads the SAME judger the operator runs (scripts/audit_fix10class24_tx_rms_sweep1.py)
and statically inspects the SAME orchestration script
(scripts/run_fix10class24_tx_rms_sweep1.sh), so the tests exercise the production
parsing/judging logic verbatim.  Pure stdlib; no board, no libiio, no icraft-run.
"""

import importlib.util
import os
import re
import shutil
import tempfile
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, ".."))
_AUDIT_PATH = os.path.normpath(os.path.join(
    _ROOT, "scripts", "audit_fix10class24_tx_rms_sweep1.py"))
_SWEEP_PATH = os.path.normpath(os.path.join(
    _ROOT, "scripts", "run_fix10class24_tx_rms_sweep1.sh"))
_RUN_TESTS_PATH = os.path.normpath(os.path.join(_HERE, "run_tests.sh"))

_spec = importlib.util.spec_from_file_location("txrms_audit", _AUDIT_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load audit at %s" % _AUDIT_PATH)
aud = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(aud)

with open(_SWEEP_PATH, "r", encoding="utf-8") as _fh:
    SWEEP = _fh.read()
with open(_RUN_TESTS_PATH, "r", encoding="utf-8") as _fh:
    RUN_TESTS = _fh.read()

_FORBIDDEN = ("RF_PASS", "SMOKE_PASS", "PROJECT_COMPLETE", "FINAL_",
              "NEW_PRODUCTION_TARGET_RMS")


def _echo_lines(script):
    """Lines of the script that actually emit output (echo/printf/heredoc bodies)."""
    out = []
    for line in script.splitlines():
        s = line.strip()
        if s.startswith("echo ") or s.startswith("echo \"") or s.startswith("printf "):
            out.append(line)
    # heredoc bodies: lines between 'cat <<EOF' and the closing 'EOF'
    in_heredoc = False
    for line in script.splitlines():
        if re.match(r"\s*cat\s+<<\s*['\"]?EOF", line):
            in_heredoc = True
            continue
        if in_heredoc and line.strip() == "EOF":
            in_heredoc = False
            continue
        if in_heredoc:
            out.append(line)
    return out


def make_singlesdr_log(rms=2048, mode="full24", gated_residual=0.05,
                       reject_residual=0.15, gated_correct=1):
    """Three holdout files: BPSK(gated), QPSK(gated), 4ASK(rejected)."""
    lines = [
        "FIX10CLASS24_BF16_SINGLESDR_FILE file=bpsk_1500.ci16 input_kind=radioml-d2-2p56m "
        "source_index=1500 source_class=3 modulation=BPSK frozen_complex=53760 split_role=holdout",
        "FIX10CLASS24_BF16_SINGLESDR_FILE file=qpsk_2500.ci16 input_kind=radioml-d2-2p56m "
        "source_index=2500 source_class=4 modulation=QPSK frozen_complex=53760 split_role=holdout",
        "FIX10CLASS24_BF16_SINGLESDR_FILE file=4ask_500.ci16 input_kind=radioml-d2-2p56m "
        "source_index=500 source_class=1 modulation=4ASK frozen_complex=53760 split_role=holdout",
        "FIX10CLASS24_BF16_SINGLESDR_CAPTURE_ATTEMPTS file=bpsk_1500.ci16 attempts=1 retries=0 final_failure=NONE final_valid=1",
        "FIX10CLASS24_BF16_SINGLESDR_RECOVERY file=bpsk_1500.ci16 computed=1 valid=1 failure=NONE "
        "timing=36074 gain_mag=0.015 phase_deg=-3.3 fine_cfo_hz=-6.2 sro_ppm=0.0 "
        "training_corr=0.99 training_residual=0.01 payload_gain_mag=0.015 "
        "payload_rms_gain_mag=0.015 payload_phase_deg=-3.3 payload_training_corr=0.99 "
        "payload_training_residual=%.6f fidelity=RF_PRESERVES_IQ rx_clipped=0" % gated_residual,
        "FIX10CLASS24_BF16_SINGLESDR_WIDE_LINEAR file=bpsk_1500.ci16 enabled=1 scalar_validation_residual=0.10 validation_residual=0.08 improvement_ratio=0.8 image_ratio=0.1 reason=ENABLED",
        "FIX10CLASS24_BF16_SINGLESDR_CAPTURE_ATTEMPTS file=qpsk_2500.ci16 attempts=2 retries=1 final_failure=NONE final_valid=1",
        "FIX10CLASS24_BF16_SINGLESDR_RECOVERY file=qpsk_2500.ci16 computed=1 valid=1 failure=NONE "
        "timing=36074 gain_mag=0.015 phase_deg=-3.3 fine_cfo_hz=5.1 sro_ppm=0.0 "
        "training_corr=0.99 training_residual=0.01 payload_gain_mag=0.015 "
        "payload_rms_gain_mag=0.015 payload_phase_deg=-3.3 payload_training_corr=0.99 "
        "payload_training_residual=%.6f fidelity=RF_PRESERVES_IQ rx_clipped=0" % gated_residual,
        "FIX10CLASS24_BF16_SINGLESDR_WIDE_LINEAR file=qpsk_2500.ci16 enabled=0 scalar_validation_residual=0.10 validation_residual=0.11 improvement_ratio=1.1 image_ratio=0.001 reason=IMAGE_TOO_SMALL",
        "FIX10CLASS24_BF16_SINGLESDR_FILE file=4ask_500.ci16 classification=SKIPPED reason=fidelity_gate fidelity=PAYLOAD_TRAINING_RESIDUAL_TOO_HIGH",
        "FIX10CLASS24_BF16_SINGLESDR_CLASSIFY file=bpsk_1500.ci16 baseline_pred=3 rf_pred=3 "
        "source_label=3 prediction_agreement=1 label_correct=1 repeat_deterministic=1 finite=1",
        "FIX10CLASS24_BF16_SINGLESDR_CLASSIFY file=qpsk_2500.ci16 baseline_pred=4 rf_pred=5 "
        "source_label=4 prediction_agreement=0 label_correct=%d repeat_deterministic=1 finite=1" % gated_correct,
    ]
    return "\n".join(lines) + "\n"


def make_dualsdr_log():
    lines = [
        "FIX10CLASS24_BF16_FILE file=bpsk_1500.ci16 input_kind=radioml-d2-2p56m "
        "source_index=1500 source_class=3 modulation=BPSK frozen_complex=53760 split_role=holdout",
        "FIX10CLASS24_BF16_CAPTURE_ATTEMPTS file=bpsk_1500.ci16 attempts=1 retries=0 final_failure=NONE final_valid=1",
        "FIX10CLASS24_BF16_RECOVERY file=bpsk_1500.ci16 computed=1 valid=1 failure=NONE "
        "timing=36074 gain_mag=0.015 phase_deg=-3.3 fine_cfo_hz=0.25 sro_ppm=0.0 "
        "training_corr=0.99 training_residual=0.01 payload_gain_mag=0.015 "
        "payload_rms_gain_mag=0.015 payload_phase_deg=-3.3 payload_training_corr=0.999 "
        "payload_training_residual=0.030000 fidelity=RF_PRESERVES_IQ rx_clipped=0",
        "FIX10CLASS24_BF16_WIDE_LINEAR file=bpsk_1500.ci16 enabled=1 scalar_validation_residual=0.10 validation_residual=0.08 improvement_ratio=0.8 image_ratio=0.1 reason=ENABLED",
        "FIX10CLASS24_BF16_CLASSIFY file=bpsk_1500.ci16 baseline_pred=3 rf_pred=3 "
        "source_label=3 prediction_agreement=1 label_correct=1 repeat_deterministic=1 finite=1",
    ]
    return "\n".join(lines) + "\n"


def _config_meta(link, rms, mode="full24", run=1):
    return ("FIX10CLASS24_TX_RMS_SWEEP1_CONFIG link=%s mode=%s\n"
            "FIX10CLASS24_TX_RMS_SWEEP1_CONFIG requested_target_rms=%s run=%s\n"
            % (link, mode, rms, run))


class TestRmsLevelsStrict(unittest.TestCase):
    def test_01_levels_exactly_2048_1536_1024(self):
        self.assertEqual(tuple(aud.RMS_LEVELS), (2048, 1536, 1024))
        m = re.search(r'2048\|1536\|1024\)', SWEEP)
        self.assertIsNotNone(m)
        # No RMS value outside {2048,1536,1024} may be passed to a runner.
        for bad in ("--target-rms=2049", "--target-rms=0", "--target-rms=4096",
                    "--rf-tx-target-rms=2049", "--rf-tx-target-rms=4096"):
            self.assertNotIn(bad, SWEEP)


class TestTxAttenCeiling(unittest.TestCase):
    def test_02_tx_atten_fixed_minus40(self):
        self.assertIn("TX_ATTEN=-40", SWEEP)
        self.assertIn("--tx-atten -40", SWEEP)
        for bad in ("--tx-atten -35", "--tx-atten -30", "--tx-atten=-35"):
            self.assertNotIn(bad, SWEEP)


class TestNoForbiddenVerdictTokens(unittest.TestCase):
    def test_03_no_forbidden_token_is_printed(self):
        for line in _echo_lines(SWEEP):
            for tok in _FORBIDDEN:
                self.assertNotIn(tok, line,
                                 "forbidden token %r printed by output line: %s" % (tok, line))


class TestSingleDualWiring(unittest.TestCase):
    def test_04_single_forbids_tx_control(self):
        self.assertIn("single link must NOT use a PC TX service", SWEEP)
        self.assertIn('if [ "$LINK" = "single" ] && [ -n "$TX_CONTROL" ]', SWEEP)

    def test_05_dual_requires_tx_control(self):
        self.assertIn("dual link requires --tx-control", SWEEP)
        self.assertIn('if [ "$LINK" = "dual" ] && [ -z "$TX_CONTROL" ]', SWEEP)

    def test_06_refuse_overwrite(self):
        self.assertIn("output run dir already exists (refuse overwrite)", SWEEP)
        self.assertIn('[ -e "$RUN_DIR" ]', SWEEP)

    def test_07_pc_tx_command_uses_same_rms(self):
        # The PC TX command must carry the SAME target RMS as the board round.
        self.assertIn("--rf-tx-target-rms ${TARGET_RMS}", SWEEP)
        self.assertIn("--rf-tx-target-rms=\"$TARGET_RMS\"", SWEEP)


class TestParseSingleSdr(unittest.TestCase):
    def test_08_singlesdr_metrics(self):
        samples = aud.parse_run(make_singlesdr_log())
        self.assertEqual(len(samples), 3)
        self.assertTrue(samples[1500].gated)
        self.assertTrue(samples[2500].gated)
        self.assertFalse(samples[500].gated)
        m = aud.compute_config_metrics(samples)
        self.assertEqual(m["scored"], 2)
        self.assertEqual(m["rf_excluded"], 1)
        self.assertAlmostEqual(m["coverage"], 2 / 3)
        self.assertAlmostEqual(m["gated_accuracy"], 1.0)
        self.assertAlmostEqual(m["end_to_end_accuracy"], 2 / 3)
        self.assertAlmostEqual(m["wide_linear_enabled_ratio"], 0.5)
        self.assertAlmostEqual(m["capture_attempts_mean"], 1.5)
        self.assertAlmostEqual(m["residual_mean"], 0.05)


class TestParseDualSdr(unittest.TestCase):
    def test_09_dualsdr_prefix(self):
        samples = aud.parse_run(make_dualsdr_log())
        self.assertEqual(len(samples), 1)
        self.assertTrue(samples[1500].gated)
        self.assertAlmostEqual(samples[1500].payload_training_residual, 0.03)
        self.assertEqual(samples[1500].wide_linear_enabled, 1)
        m = aud.compute_config_metrics(samples)
        self.assertEqual(m["scored"], 1)
        self.assertEqual(m["rf_excluded"], 0)
        self.assertAlmostEqual(m["gated_accuracy"], 1.0)


class TestForcedHybridLabeling(unittest.TestCase):
    def test_10_rejected_forced_is_diagnostic_bypass(self):
        samples = aud.parse_run(make_singlesdr_log())
        forced = [{"source_index": 500, "source_class": 1, "rf_pred": 1,
                   "label_correct": 1, "diagnostic_bypass": 1}]
        m = aud.compute_config_metrics(samples, forced)
        self.assertTrue(m["forced_available"])
        self.assertEqual(m["forced_count"], 1)
        self.assertEqual(m["forced_correct"], 1)
        # 2 gated correct + 1 forced correct over 3 holdout = 1.0
        self.assertAlmostEqual(m["forced_raw24_accuracy"], 1.0)

    def test_11_no_forced_is_pending(self):
        samples = aud.parse_run(make_singlesdr_log())
        m = aud.compute_config_metrics(samples)
        self.assertFalse(m["forced_available"])
        self.assertEqual(m["forced_count"], 0)


class TestStructuralFailClosed(unittest.TestCase):
    def test_12_missing_config_meta_or_bad_name(self):
        tmp = tempfile.mkdtemp(prefix="txrms_test_")
        try:
            rd = os.path.join(tmp, "single_bf16_rms2048_run1")
            os.mkdir(rd)
            with open(os.path.join(rd, "run.log"), "w") as fh:
                fh.write(make_singlesdr_log())
            # missing config.meta -> ParseError
            with self.assertRaises(aud.ParseError):
                aud.collect_runs(tmp, "single", re.compile(r"^(single|dual)_bf16_rms(\d+)_run([123])$"))
            # now add meta with a WRONG rms (2049 dir is impossible, so mismatch link)
            with open(os.path.join(rd, "config.meta"), "w") as fh:
                fh.write(_config_meta("dual", 2048))  # link mismatch
            with self.assertRaises(aud.ParseError):
                aud.collect_runs(tmp, "single", re.compile(r"^(single|dual)_bf16_rms(\d+)_run([123])$"))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_13_config_meta_parser(self):
        tmp = tempfile.mkdtemp(prefix="txrms_meta_")
        try:
            rd = os.path.join(tmp, "single_bf16_rms1536_run2")
            os.mkdir(rd)
            with open(os.path.join(rd, "config.meta"), "w") as fh:
                fh.write(_config_meta("single", 1536, mode="short2", run=2))
            meta = aud._read_config_meta(rd)
            self.assertEqual(meta["requested_target_rms"], 1536)
            self.assertEqual(meta["link"], "single")
            self.assertEqual(meta["mode"], "short2")
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestFullSuiteWiring(unittest.TestCase):
    def test_14_new_test_wired_into_full_suite(self):
        self.assertIn("test_fix10class24_tx_rms_sweep1.py", RUN_TESTS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
