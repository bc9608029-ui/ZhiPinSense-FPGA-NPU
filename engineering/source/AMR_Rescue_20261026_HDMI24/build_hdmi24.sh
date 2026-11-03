#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p bin
g++ -std=gnu++17 -O2 -Wall -Wextra -Werror -Iboard_package -Isdr_adapter -Iui_sw \
 board_package/board_ui_live_rml24.cpp ui_sw/direct_framebuffer_backend.cpp \
 ui_sw/font_atlas.cpp ui_sw/font_atlas_data.cpp ui_sw/ui_render.cpp -o bin/board_ui_live_rml24
echo HDMI24_BUILD_OK
