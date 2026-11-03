from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "amr_rescue_gmsk_candidate_20261026" / "validation_seed5100000"
SPEC = importlib.util.spec_from_file_location("rml24_final_tx", ROOT / "pc_runtime" / "rml24_final_tx.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PcTxTests(unittest.TestCase):
    def test_public_manifest_has_no_labels_or_truth(self) -> None:
        path = ROOT / "pc_runtime" / "selftest_manifest_240.json"
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(document["contains_labels"])
        self.assertEqual(len(document["records"]), 240)
        self.assertTrue(all(set(row) == {"seq", "file", "source_sha256"} for row in document["records"]))

    def test_frame_builder_matches_frozen_geometry(self) -> None:
        manifest = MODULE.load_manifest(ROOT / "pc_runtime" / "selftest_manifest_240.json")
        payload = (SOURCE / manifest[0]["file"]).read_bytes()
        train = np.ones(2048, dtype=np.complex64)
        tail = np.ones(2048, dtype=np.complex64)
        frame = MODULE.build_frame(payload, train, tail)
        self.assertEqual(frame.dtype, np.complex64)
        self.assertEqual(frame.shape, (2048 + 2048 + 8192 + 2048 + 2048,))
        self.assertTrue(np.isfinite(frame).all())
        self.assertLessEqual(max(abs(frame.real).max(), abs(frame.imag).max()), 2047)


if __name__ == "__main__":
    unittest.main()
