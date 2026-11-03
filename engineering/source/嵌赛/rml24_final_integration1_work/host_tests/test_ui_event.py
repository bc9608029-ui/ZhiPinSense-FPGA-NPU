from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
from ui_event import build_board_ui_result, build_ui_event, validate_ui_event


SOURCE = ROOT.parent / "amr_rescue_gmsk_candidate_20261026"


class UiEventTests(unittest.TestCase):
    def test_valid_prediction_and_low_confidence(self) -> None:
        logits = [-1.0] * 24
        logits[4] = 0.0
        event = build_ui_event(4, {"pred": 4, "logits": logits, "input_sha256": "a" * 64}, timestamp_us=1)
        self.assertEqual(event["state"], "LOW_CONFIDENCE")
        self.assertEqual(event["prediction"]["class_name"], "QPSK")
        self.assertFalse(event["iq_valid"])
        self.assertFalse(event["spectrum_valid"])

    def test_real_tensor_generates_constellation_and_spectrum(self) -> None:
        phase = 2.0 * np.pi * 73.0 * np.arange(1024) / 1024.0
        signal = np.exp(1j * phase).astype(np.complex64)
        tensor = np.stack(
            [np.stack([signal.real, signal.imag], axis=0) for _ in range(8)],
            axis=0,
        )
        logits = [-10.0] * 24
        logits[3] = 10.0
        event = build_ui_event(9, {"pred": 3, "logits": logits}, timestamp_us=4, display_tensor=tensor)
        self.assertTrue(event["iq_valid"])
        self.assertEqual(len(event["iq_i16_interleaved"]), 512)
        self.assertGreater(event["iq_units_per_count"], 0)
        self.assertTrue(event["spectrum_valid"])
        self.assertEqual(len(event["spectrum_db_rel_x4"]), 256)
        self.assertEqual(max(event["spectrum_db_rel_x4"]), 0)
        validate_ui_event(event)
        board = build_board_ui_result(event)
        self.assertEqual(board["version"], "rml24-final-chain-v1")
        self.assertEqual(board["class_count"], 24)
        self.assertEqual(board["raw_24_top1"], 3)
        self.assertEqual(board["merged_23_top1"], -1)
        self.assertEqual(len(board["measurements"]["spectrum_dbfs_x4"]), 256)

    def test_failed_recovery_is_not_sent_as_classification(self) -> None:
        event = build_ui_event(5, {"pred": -1, "error": "no sync"}, timestamp_us=5)
        self.assertIsNone(build_board_ui_result(event))

    def test_invalid_result_is_not_forced_to_a_class(self) -> None:
        event = build_ui_event(1, {"pred": -1, "error": "no preamble"}, timestamp_us=2)
        self.assertEqual(event["state"], "RECOVERY_FAILED")
        self.assertIsNone(event["prediction"])

    def test_non_normalized_probabilities_rejected(self) -> None:
        logits = [-10.0] * 24
        logits[3] = 10.0
        event = build_ui_event(1, {"pred": 3, "logits": logits, "input_sha256": "b" * 64}, timestamp_us=3)
        event["prediction"]["probabilities"][0] = 0.5
        with self.assertRaises(ValueError):
            validate_ui_event(event)

    def test_r1_export_has_full_denominator_and_no_fake_iq(self) -> None:
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            output = Path(directory) / "r1.jsonl"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "export_ui_replay.py"),
                    "--board-results",
                    str(SOURCE / "validation_rf_r1" / "board_results.json"),
                    "--expected",
                    str(SOURCE / "validation_seed5100000" / "expected_private.json"),
                    "--out",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            events = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(events), 240)
            self.assertFalse(any(event["iq_valid"] or event["spectrum_valid"] for event in events))
            self.assertEqual(sum(event["self_test"]["correct"] for event in events), 233)


if __name__ == "__main__":
    unittest.main()

