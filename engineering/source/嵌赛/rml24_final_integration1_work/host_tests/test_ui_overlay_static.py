from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class UiOverlayStaticTests(unittest.TestCase):
    def test_final_ui_is_raw24_and_display_only(self) -> None:
        board = (ROOT / "board_ui_overlay/board_package/board_ui_live_rml24_final.cpp").read_text(encoding="utf-8")
        parser = (ROOT / "board_ui_overlay/board_package/result_frame_v2_parse.hpp").read_text(encoding="utf-8")
        render = (ROOT / "board_ui_overlay/ui_sw/ui_render.cpp").read_text(encoding="utf-8")
        self.assertIn("parse_result_frame_rml24_final", board)
        self.assertIn("case 2: ui::render_constellation", board)
        self.assertIn("RML24-BF16-RAW", parser)
        self.assertIn("RAW24_UNMERGED", parser)
        self.assertIn("IQ display width mismatch", parser)
        self.assertIn("CONSTELLATION", render)
        self.assertIn("display-only", render)
        self.assertNotIn("expected_private", board + parser + render)

    def test_spectrum_is_not_mislabeled_dbfs(self) -> None:
        waterfall = (ROOT / "board_ui_overlay/ui_sw/waterfall_render.cpp").read_text(encoding="utf-8")
        self.assertIn("dB REL", waterfall)
        self.assertIn("relative to frame peak", waterfall)


if __name__ == "__main__":
    unittest.main()
