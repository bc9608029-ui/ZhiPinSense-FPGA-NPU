#!/usr/bin/env bash
# Build and run the comprehensive RML23 UI snapshot generator.  `outdir` is the
# absolute-or-relative destination (default ../artifacts/ui_rml23).
set -uo pipefail
cd "$(dirname "$0")"
OUT="${1:-../artifacts/ui_rml23}"
FLAGS="-std=gnu++17 -O2 -Wall -Wextra -Werror -I../board_package -I../sdr_adapter -I../ui_sw"
g++ $FLAGS make_ui_rml23_snapshots.cpp ../ui_sw/font_atlas.cpp ../ui_sw/font_atlas_data.cpp ../ui_sw/ui_render.cpp -o bin/make_ui_rml23_snapshots
mkdir -p "$OUT"
./bin/make_ui_rml23_snapshots "$OUT"
echo "snapshot exit=$?"
ls -1 "$OUT"/*.ppm | wc -l
