from pathlib import Path

root = Path(__file__).resolve().parents[1] / "ui_fivepage_candidate"
touch = (root / "board_package" / "touch_geometry.hpp").read_text(encoding="utf-8")
main = (root / "board_package" / "board_ui_live_rml24_final.cpp").read_text(encoding="utf-8")
render = (root / "ui_sw" / "ui_render.cpp").read_text(encoding="utf-8")

checks = {
    "five_tabs": "constexpr int kTabCount = 5;" in touch,
    "nav_labels": '"CLASSIFY", "MEASURE", "WATERFALL", "CONSTELLATION", "SETUP"' in render,
    "measure_page": "case 1: ui::render_parameters" in main,
    "waterfall_page": "case 2: ui::render_waterfall" in main,
    "constellation_page": "case 3: ui::render_constellation" in main,
    "setup_page": "case 4: ui::render_mode" in main,
    "controls_only_page5": "touch_nav.active_page() != 4" in main,
    "top3_policy": "if (false && st.class_count >= 23)" in render,
    "dedicated_waterfall": "void render_waterfall(" in render,
}

for name, ok in checks.items():
    print(f"{name}={'PASS' if ok else 'FAIL'}")
if not all(checks.values()):
    raise SystemExit(1)
print(f"FIVEPAGE_STATIC_AUDIT result=PASS checks={len(checks)}")
