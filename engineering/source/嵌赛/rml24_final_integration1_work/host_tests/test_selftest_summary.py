from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "amr_rescue_gmsk_candidate_20261026"
SPEC = importlib.util.spec_from_file_location("summarize_selftest", ROOT / "scripts" / "summarize_selftest.py")
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class SelftestSummaryTests(unittest.TestCase):
    def test_frozen_two_round_result(self) -> None:
        summary = MODULE.summarize(
            SOURCE / "validation_seed5100000" / "expected_private.json",
            [
                SOURCE / "validation_rf_r1" / "board_results.json",
                SOURCE / "validation_rf_r2" / "board_results.json",
            ],
        )
        combined = summary["combined"]
        self.assertEqual(combined["total"], 480)
        self.assertEqual(combined["arms"]["baseline"]["correct"], 403)
        self.assertEqual(combined["arms"]["candidate"]["correct"], 463)
        self.assertEqual(combined["arms"]["baseline"]["failures"], 0)
        self.assertEqual(combined["arms"]["candidate"]["failures"], 0)
        self.assertEqual(len(combined["fixes"]), 60)
        self.assertEqual(combined["regressions"], [])
        self.assertTrue(combined["strict_no_regression_gate"])
        self.assertTrue(all(row["total"] == 20 for row in combined["arms"]["candidate"]["per_class"]))


if __name__ == "__main__":
    unittest.main()
