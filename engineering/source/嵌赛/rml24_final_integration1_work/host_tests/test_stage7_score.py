from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from score_stage7_run import score


class Stage7ScoreTests(unittest.TestCase):
    def test_missing_and_failed_rows_remain_in_denominator(self) -> None:
        expected = {
            "records": [
                {"seq": seq, "class_index": seq // 10, "class_name": f"C{seq // 10}"}
                for seq in range(240)
            ]
        }
        records = []
        for seq in range(239):
            pred = seq // 10
            arm = {"pred": pred}
            if seq == 1:
                arm = {"pred": -1, "error": "recovery failed"}
            records.append({"seq": seq, "arms": {"candidate": arm}})
        with tempfile.TemporaryDirectory(dir=ROOT) as directory:
            root = Path(directory)
            expected_path = root / "expected.json"
            results_path = root / "results.json"
            expected_path.write_text(json.dumps(expected), encoding="utf-8")
            results_path.write_text(json.dumps({"records": records}), encoding="utf-8")
            summary = score(expected_path, results_path)
        self.assertEqual(summary["total"], 240)
        self.assertEqual(summary["correct"], 238)
        self.assertEqual(summary["failure_count"], 2)
        self.assertEqual(summary["missing_sequences"], [239])


if __name__ == "__main__":
    unittest.main()
