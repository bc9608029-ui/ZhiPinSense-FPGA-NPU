from __future__ import annotations

import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class BoardEntryStaticTests(unittest.TestCase):
    def test_python_files_parse(self) -> None:
        for path in sorted(ROOT.rglob("*.py")):
            if "host_tests" in path.parts:
                continue
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

    def test_candidate_is_default_and_paired_is_explicit(self) -> None:
        source = (ROOT / "board_runtime" / "rml24_final_receiver.py").read_text(encoding="utf-8")
        self.assertIn('choices=("candidate", "paired"), default="candidate"', source)
        self.assertIn('if args.mode == "paired" else None', source)

    def test_launcher_checks_all_frozen_inputs(self) -> None:
        source = (ROOT / "board_runtime" / "run_final_receiver.sh").read_text(encoding="utf-8")
        for digest in (
            "e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a",
            "c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151",
            "28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42",
        ):
            self.assertIn(digest, source)

    def test_ui_socket_is_fail_soft_and_final_named(self) -> None:
        source = (ROOT / "board_runtime" / "rml24_final_receiver.py").read_text(encoding="utf-8")
        launcher = (ROOT / "board_runtime" / "run_final_receiver.sh").read_text(encoding="utf-8")
        self.assertIn("class UiSocketClient", source)
        self.assertIn("RML24_FINAL_UI_SEND status=RETRY", source)
        self.assertIn("/run/sdr_amr_ui_rml24_final.sock", source)
        self.assertIn("--ui-socket", launcher)


if __name__ == "__main__":
    unittest.main()

