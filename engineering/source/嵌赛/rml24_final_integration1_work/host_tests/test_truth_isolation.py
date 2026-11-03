from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class TruthIsolationTests(unittest.TestCase):
    def test_board_installer_does_not_copy_test_evidence(self) -> None:
        text = (ROOT / "deploy" / "install_overlay.sh").read_text(encoding="utf-8")
        copy_loop = next(line for line in text.splitlines() if line.startswith("for directory in "))
        self.assertNotIn("evidence", copy_loop)
        self.assertNotIn("pc_runtime", copy_loop)
        self.assertNotIn("scripts", copy_loop)

    def test_receiver_never_mentions_private_truth(self) -> None:
        text = (ROOT / "board_runtime" / "rml24_final_receiver.py").read_text(encoding="utf-8").lower()
        self.assertNotIn("expected_private", text)
        self.assertNotIn("class_index", text)
        self.assertNotIn("ground_truth", text)


if __name__ == "__main__":
    unittest.main()
