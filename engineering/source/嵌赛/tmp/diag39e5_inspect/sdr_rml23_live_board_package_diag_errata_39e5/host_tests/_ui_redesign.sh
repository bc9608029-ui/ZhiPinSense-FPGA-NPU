#!/usr/bin/env bash
# Task B scratch: rebuild + run the 5 UI host tests (incl. the new boundary test).
set -uo pipefail
cd "$(dirname "$0")"

FLAGS="-std=gnu++17 -O2 -Wall -Wextra -Werror -I../board_package -I../sdr_adapter -I../ui_sw"
CXX="${CXX:-g++}"
mkdir -p bin

echo "== rebuild UI tests =="
$CXX $FLAGS test_ui_live.cpp       ../ui_sw/font_atlas.cpp ../ui_sw/font_atlas_data.cpp ../ui_sw/ui_render.cpp -o bin/test_ui_live
$CXX $FLAGS test_ui_v3_pages.cpp   ../ui_sw/font_atlas.cpp ../ui_sw/font_atlas_data.cpp ../ui_sw/ui_render.cpp -o bin/test_ui_v3_pages
$CXX $FLAGS test_ui_layout_m19.cpp ../ui_sw/font_atlas.cpp ../ui_sw/font_atlas_data.cpp ../ui_sw/ui_render.cpp -o bin/test_ui_layout_m19
$CXX $FLAGS test_ui_rml23.cpp      ../ui_sw/font_atlas.cpp ../ui_sw/font_atlas_data.cpp ../ui_sw/ui_render.cpp -o bin/test_ui_rml23
$CXX $FLAGS test_ui_boundary.cpp   ../ui_sw/font_atlas.cpp ../ui_sw/font_atlas_data.cpp ../ui_sw/ui_render.cpp -o bin/test_ui_boundary

echo "== run UI tests =="
rc=0
./bin/test_ui_live          || rc=1
./bin/test_ui_v3_pages      || rc=1
./bin/test_ui_layout_m19    || rc=1
./bin/test_ui_rml23         || rc=1
./bin/test_ui_boundary      || rc=1
exit $rc
