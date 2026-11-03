from __future__ import annotations

import hashlib
import importlib.util
import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "runtime"))
sys.path.insert(0, str(ROOT / "recovery"))

import candidate_two_dc
from receiver_core import recover_frame, summarize_logits, tensorize


class CandidateAndCoreTests(unittest.TestCase):
    def test_candidate_is_frozen_byte_for_byte(self) -> None:
        digest = hashlib.sha256((ROOT / "recovery" / "candidate_two_dc.py").read_bytes()).hexdigest()
        self.assertEqual(digest, "e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a")

    def test_synthetic_public_frame_recovery(self) -> None:
        rng = np.random.default_rng(77)
        payload = (rng.standard_normal(8192) + 1j * rng.standard_normal(8192)).astype(np.complex64)
        burst = np.concatenate([candidate_two_dc.train, payload, candidate_two_dc.tail])
        raw = np.zeros(65536, dtype=np.complex64)
        offset = 4096
        cfo_hz = 75.0
        n = np.arange(len(burst))
        raw[offset : offset + len(burst)] = (
            1.7 * burst * np.exp(2j * np.pi * cfo_hz * n / candidate_two_dc.FS) + (0.15 + 0.05j)
        )
        frame = recover_frame(raw, candidate_two_dc.recover)
        self.assertEqual(frame.tensor.shape, (8, 2, 1024))
        self.assertEqual(len(frame.tensor_bytes), 65536)
        self.assertTrue(np.isfinite(frame.tensor).all())
        self.assertAlmostEqual(frame.metadata["cfo_hz"], cfo_hz, places=6)
        restored = frame.tensor[:, 0] + 1j * frame.tensor[:, 1]
        nrmse = np.linalg.norm(restored.reshape(-1) - payload) / np.linalg.norm(payload)
        self.assertLess(float(nrmse), 0.001)

    def test_tensor_contract_rejects_wrong_shape_and_nonfinite(self) -> None:
        with self.assertRaises(ValueError):
            tensorize(np.zeros((1, 1024), dtype=np.complex64))
        broken = np.zeros((8, 1024), dtype=np.complex64)
        broken[0, 0] = complex(np.nan, 0)
        with self.assertRaises(ValueError):
            tensorize(broken)

    def test_logit_aggregation(self) -> None:
        logits = np.full((8, 24), -3.0, dtype=np.float32)
        logits[:, 22] = 4.0
        summary = summarize_logits(logits)
        self.assertEqual(summary["pred"], 22)
        self.assertEqual(summary["class_name"], "GMSK")
        self.assertEqual(summary["window_predictions"], [22] * 8)
        self.assertEqual(summary["top3"][0]["index"], 22)

    def test_formal_entry_contains_no_truth_input(self) -> None:
        entry = (ROOT / "board_runtime" / "rml24_final_receiver.py").read_text(encoding="utf-8")
        for forbidden in ("expected_private", "--expected", "--label", "message[\"class", "message['class"):
            self.assertNotIn(forbidden, entry)
        self.assertIn('if set(message) - {"seq"}:', entry)


if __name__ == "__main__":
    unittest.main()

