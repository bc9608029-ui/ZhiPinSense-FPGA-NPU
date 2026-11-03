#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""test_four_way_oqpsk_scalar_wl.py -- host tests for the fix10class24-scalarwl-4way
four-way comparison script + the single-SDR board script that feeds it.

Loads the SAME four-way script the operator runs
(scripts/four_way_oqpsk_scalar_wl.py) and statically inspects the SAME board script
(scripts/run_fix10class24_singlesdr_scalarwl.sh), so the tests exercise the production
four-way math + the scalar/WL x BF16/mixed contract verbatim.  Pure offline: no board,
no libiio, no icraft-run, no model.
"""

import importlib.util
import os
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(_HERE, ".."))
_FW_PATH = os.path.normpath(os.path.join(
    _ROOT, "scripts", "four_way_oqpsk_scalar_wl.py"))
_BOARD_PATH = os.path.normpath(os.path.join(
    _ROOT, "scripts", "run_fix10class24_singlesdr_scalarwl.sh"))
_RUN_TESTS_PATH = os.path.normpath(os.path.join(_HERE, "run_tests.sh"))

_spec = importlib.util.spec_from_file_location("four_way_oqpsk_scalar_wl", _FW_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError("cannot load four-way script at %s" % _FW_PATH)
fw = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fw)

with open(_BOARD_PATH, "r", encoding="utf-8") as _fh:
    BOARD = _fh.read()
with open(_RUN_TESTS_PATH, "r", encoding="utf-8") as _fh:
    RUN_TESTS = _fh.read()


def _logits(argmax):
    import numpy as np
    v = np.full(fw.EXPECT_CLASS_COUNT, -10.0)
    v[argmax] = 5.0
    v[(argmax + 1) % fw.EXPECT_CLASS_COUNT] = 3.0
    return v.tolist()


def _manifest():
    return {
        "source_index": 11500,
        "source_class": 23,
        "source_label": "OQPSK",
        "modulation": "OQPSK",
        "snr_db": 18.0,
        "split_role": "holdout",
        "baseline_pred": 23,
        "fidelity_verdict": "RF_PRESERVES_IQ",
        "recovery_valid": True,
        "payload_training_residual": 0.05,
        "wide_linear_enabled": False,
        "wl_recomputed": True,
        "inputs_identical": False,
    }


class TestIdentity(unittest.TestCase):
    def test_01_label_order(self):
        self.assertEqual(len(fw.LABEL_ORDER_24), 24)
        self.assertEqual(fw.LABEL_ORDER_24[0], "OOK")
        self.assertEqual(fw.LABEL_ORDER_24[23], "OQPSK")
        self.assertEqual(len(set(fw.LABEL_ORDER_24)), 24)

    def test_02_mixed_model_identity(self):
        self.assertEqual(fw.NETWORK_NAME, "model_24class")
        self.assertEqual(fw.EXPECT_CLASS_COUNT, 24)
        self.assertEqual(len(fw.MIXED_MODEL_JSON_SHA256), 64)
        self.assertEqual(len(fw.MIXED_MODEL_RAW_SHA256), 64)
        self.assertEqual(fw.MIXED_MODEL_DIR, "model_rml23")
        self.assertEqual(fw.MIXED_MODEL_JSON_NAME, "model_24class_ZG.json")
        self.assertEqual(fw.MIXED_MODEL_RAW_NAME, "model_24class_ZG.raw")


class TestFourWayMath(unittest.TestCase):
    def test_03_all_agree(self):
        r = fw.build_four_way(_manifest(), _logits(23), _logits(23),
                              _logits(23), _logits(23))
        for k in r["cells"]:
            self.assertEqual(r["cells"][k]["argmax"], 23)
            self.assertEqual(r["cells"][k]["label"], "OQPSK")
            self.assertEqual(r["cells"][k]["label_correct"], 1)
            self.assertEqual(r["cells"][k]["baseline_agreement"], 1)
        self.assertTrue(r["agreement"]["all_four"])
        self.assertTrue(r["agreement"]["scalar_bf16_mixed"])
        self.assertTrue(r["agreement"]["bf16_scalar_wl"])

    def test_04_wl_mixed_disagrees(self):
        r = fw.build_four_way(_manifest(), _logits(23), _logits(23),
                              _logits(23), _logits(7))
        self.assertEqual(r["cells"]["wl_mixed"]["label"], "32PSK")
        self.assertTrue(r["agreement"]["scalar_bf16_mixed"])
        self.assertFalse(r["agreement"]["wl_bf16_mixed"])
        self.assertFalse(r["agreement"]["mixed_scalar_wl"])
        self.assertTrue(r["agreement"]["bf16_scalar_wl"])
        self.assertFalse(r["agreement"]["all_four"])

    def test_05_nonfinite_never_agrees(self):
        bad = [float("nan")] * fw.EXPECT_CLASS_COUNT
        r = fw.build_four_way(_manifest(), _logits(23), _logits(23), bad, bad)
        self.assertFalse(r["cells"]["scalar_mixed"]["finite"])
        self.assertFalse(r["agreement"]["scalar_bf16_mixed"])
        self.assertFalse(r["agreement"]["all_four"])

    def test_06_wrong_but_consistent(self):
        r = fw.build_four_way(_manifest(), _logits(1), _logits(1),
                              _logits(1), _logits(1))
        self.assertTrue(all(r["cells"][k]["argmax"] == 1 for k in r["cells"]))
        self.assertTrue(all(r["cells"][k]["label_correct"] == 0 for k in r["cells"]))
        self.assertTrue(r["agreement"]["all_four"])

    def test_07_self_test_passes(self):
        self.assertEqual(fw.self_test(), 0)


class TestBoardScriptContract(unittest.TestCase):
    def test_08_oqpsk_single_sdr(self):
        # The board script measures EXACTLY OQPSK(source_index=11500), single SDR.
        self.assertIn("SOURCE_INDEX=11500", BOARD)
        self.assertIn('--source-index="$SOURCE_INDEX"', BOARD)
        self.assertIn("--phase=iq-rf-loopback-24class-bf16-scalarwl", BOARD)
        # Single-SDR: no PC TX / TCP control channel.
        for banned in ("--tx-control", "tcp://", "39010", "PC_TX_IP", "--pc-tx"):
            self.assertNotIn(banned, BOARD)
        self.assertIn("--rx-uri=\"$RX_URI\"", BOARD)
        self.assertNotIn("--tx-uri", BOARD)

    def test_09_no_dump_failed_rx_no_aggregator(self):
        # This is a MEASUREMENT, not an accuracy run: no per-class A/B dump and no
        # forced-accuracy aggregator; the board produces the BF16 pair + two inputs.
        self.assertNotIn("--dump-failed-rx", BOARD)
        self.assertNotIn("aggregate_fix10class24", BOARD)
        self.assertNotIn("forced_raw24_accuracy", BOARD)

    def test_10_mixed_model_dir_correct(self):
        # The offline mixed-precision model is model_rml23/model_24class_ZG.
        self.assertIn("model_rml23", BOARD)
        self.assertNotIn("model_rml24_23class_ZG", BOARD)
        self.assertIn("four_way_oqpsk_scalar_wl.py", BOARD)
        self.assertIn("--phase mixed-precision", BOARD)
        self.assertIn("--phase four-way", BOARD)

    def test_11_tx_atten_safety_ceiling(self):
        self.assertIn("TX_ATTEN=-40", BOARD)
        for bad in ("-35", "-30", "-25"):
            self.assertNotIn("TX_ATTEN=%s" % bad, BOARD)


class TestWiring(unittest.TestCase):
    def test_12_new_test_wired_into_suite(self):
        self.assertIn("test_four_way_oqpsk_scalar_wl.py", RUN_TESTS)


if __name__ == "__main__":
    unittest.main(verbosity=2)
