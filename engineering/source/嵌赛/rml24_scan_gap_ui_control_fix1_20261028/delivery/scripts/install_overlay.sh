#!/usr/bin/env bash
set -euo pipefail

usage() { echo "usage: $0 --base EXISTING_CANDIDATE --out NEW_TEST_TREE" >&2; }
BASE=""; OUT=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --base) BASE="$2"; shift 2 ;;
    --out) OUT="$2"; shift 2 ;;
    *) usage; exit 2 ;;
  esac
done
[ -n "$BASE" ] && [ -n "$OUT" ] || { usage; exit 2; }
[ -d "$BASE/rml24_final" ] && [ -d "$BASE/board_package" ] && [ -d "$BASE/ui_sw" ] || {
  echo "invalid base tree" >&2; exit 2; }
[ ! -e "$OUT" ] || { echo "refusing existing output: $OUT" >&2; exit 2; }

check() { printf '%s  %s\n' "$1" "$2" | sha256sum -c -; }
check 4448eda5b943ed2f883631f938cd7dfa94bbcc660494ff34d0d9463ffa0ff85e "$BASE/rml24_final/board_runtime/standalone_receiver.py"
check 0676cdb061a2f2b9ebe359fcfde59767236139acb01ed77ce76ab2e0fbb44fa6 "$BASE/ui_sw/ui_render.hpp"
check d3342db059dd439c1dd0cc824d24f13c5784ab0774f3b466a29fa576513b3e34 "$BASE/ui_sw/ui_render.cpp"
check c5ef30cb29e9cbd63088ed17a6729e7ac3c711c196938609b1e18d433b78b0b0 "$BASE/board_package/touch_mode_control.hpp"
check fea14cb51eaac09acd61fccc7ddec2e24a0f82810c5676fe24712ce74a3ab044 "$BASE/board_package/board_ui_live_rml24_final.cpp"

HERE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cp -a -- "$BASE" "$OUT"
cp -a -- "$HERE/overlay/." "$OUT/."
echo "INSTALL_RESULT result=PASS out=$OUT base_preserved=1"
