#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BASE="${1:-$ROOT/../fix10class24_waterfall1_work/sdr_rml24_fix10class24_waterfall1}"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

bash "$ROOT/deploy/assemble_stage7_board_tree.sh" \
  --base-source "$BASE" \
  --overlay-source "$ROOT" \
  --out-tree "$TMP/board_tree"

cd "$TMP/board_tree"
bash board_package/build_ui_live_rml24_final.sh
test -x bin/board_ui_live_rml24_final
file bin/board_ui_live_rml24_final
echo "RML24_FINAL_UI_FULL_BUILD result=PASS"
