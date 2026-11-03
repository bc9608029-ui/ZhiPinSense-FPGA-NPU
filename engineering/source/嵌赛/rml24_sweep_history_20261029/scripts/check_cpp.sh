#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p evidence/bin
g++ -std=c++17 -O2 -Wall -Wextra -Werror tests/test_history_ui.cpp candidate/ui_sw/font_atlas.cpp candidate/ui_sw/font_atlas_data.cpp candidate/ui_sw/ui_render.cpp candidate/ui_sw/waterfall_render.cpp -o evidence/bin/test_history_ui
./evidence/bin/test_history_ui
g++ -std=c++17 -O2 -Wall -Wextra -Werror tests/render_preview.cpp candidate/ui_sw/font_atlas.cpp candidate/ui_sw/font_atlas_data.cpp candidate/ui_sw/ui_render.cpp candidate/ui_sw/waterfall_render.cpp -o evidence/bin/render_preview
./evidence/bin/render_preview
bash candidate/board_package/build_ui_live_rml24_final.sh
echo SOFTWARE_CPP_CHECK_PASS
