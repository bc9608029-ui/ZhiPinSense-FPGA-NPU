#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 --base-source DIR --overlay-source DIR --out-tree DIR" >&2
}

BASE=""
OVERLAY=""
OUT=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --base-source) BASE="$2"; shift 2 ;;
    --overlay-source) OVERLAY="$2"; shift 2 ;;
    --out-tree) OUT="$2"; shift 2 ;;
    *) usage; exit 2 ;;
  esac
done

[ -n "$BASE" ] && [ -n "$OVERLAY" ] && [ -n "$OUT" ] || { usage; exit 2; }
[ -d "$BASE/board_package" ] && [ -d "$BASE/ui_sw" ] && [ -d "$BASE/sdr_adapter" ] || {
  echo "base-source is not the validated waterfall UI tree: $BASE" >&2; exit 2;
}
[ -f "$OVERLAY/contract/final_system_contract.json" ] || {
  echo "overlay-source is not the RML24 final integration tree: $OVERLAY" >&2; exit 2;
}
[ ! -e "$OUT" ] || { echo "out-tree already exists: $OUT" >&2; exit 2; }

mkdir -p "$OUT"
cp -a "$BASE/." "$OUT/"

for directory in board_package sdr_adapter ui_sw; do
  if [ -d "$OVERLAY/board_ui_overlay/$directory" ]; then
    cp -a "$OVERLAY/board_ui_overlay/$directory/." "$OUT/$directory/"
  fi
done

mkdir -p "$OUT/rml24_final"
for directory in board_runtime contract recovery runtime docs; do
  cp -a "$OVERLAY/$directory" "$OUT/rml24_final/"
done
cp "$OVERLAY/README.md" "$OUT/rml24_final/README.md"

echo 'e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a  '"$OUT/rml24_final/recovery/candidate_two_dc.py" | sha256sum -c -
test -f "$OUT/board_package/board_ui_live_rml24_final.cpp"
test -x "$OUT/board_package/build_ui_live_rml24_final.sh"

if find "$OUT/rml24_final" -type f | grep -E '/(truth|evidence|pc_runtime)/|expected_private|selftest_manifest' >/dev/null; then
  echo "truth/private test material leaked into board tree" >&2
  exit 1
fi

echo "RML24_FINAL_STAGE7_ASSEMBLE result=PASS out_tree=$OUT"
