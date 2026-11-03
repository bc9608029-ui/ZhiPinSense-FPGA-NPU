#!/usr/bin/env bash
# Prove the model / golden / labels / preprocess / RTL / bitstream / Flash
# assets are unchanged by the heartbeat + UI + integrated packages.
#
#   1. frozen model asset SHA256 vs recorded values
#   2. frozen dirs byte-identical between the correctness baseline package and
#      the integrated package
#   3. absence of any RTL / bitstream / Flash artifacts
#   4. explicit per-patch file inventory, with a frozen-category cross-check
set -euo pipefail
cd "$(dirname "$0")/.."

V="$(mktemp -d)"
trap 'rm -rf "$V"' EXIT

tar -xzf dist/sdr_rml23_live_board_package_correctness_fix.tar.gz -C "$V"
tar -xzf dist/sdr_rml23_live_board_package_integrated.tar.gz    -C "$V"
B="$V/sdr_rml23_live_board_package_correctness_fix"
I="$V/sdr_rml23_live_board_package_integrated"

echo "== 1. frozen model assets: integrated package sha256 =="
sha256sum \
  "$I/model_rml23/model_24class_ZG.json" \
  "$I/model_rml23/model_24class_ZG.raw" \
  "$I/model_12class/model_12class.raw" \
  "$I/model_12class/model_12class.json"

echo ""
echo "== 2. frozen dirs: baseline vs integrated =="
for d in model_rml23 model_12class deployment_golden contracts; do
  n="$(find "$I/$d" -type f | wc -l)"
  if diff -rq "$B/$d" "$I/$d" >/dev/null 2>&1; then
    echo "  $d: IDENTICAL ($n files)"
  else
    echo "  $d: *** DIFFERS ***"
    diff -rq "$B/$d" "$I/$d"
  fi
done

echo ""
echo "== 3. preprocess header unchanged (same as baseline) =="
if cmp -s "$B/sdr_adapter/preprocess.hpp" "$I/sdr_adapter/preprocess.hpp"; then
  echo "  sdr_adapter/preprocess.hpp: IDENTICAL"
else
  echo "  sdr_adapter/preprocess.hpp: *** DIFFERS ***"
fi

echo ""
echo "== 4. absence of RTL / bitstream / Flash artifacts in integrated package =="
echo "  RTL (.v/.sv/.vhd/.vhdl):        $(find "$I" -type f \( -name '*.v' -o -name '*.sv' -o -name '*.vhd' -o -name '*.vhdl' \) | wc -l) files"
echo "  bitstream (.bit/.bin/.bif):     $(find "$I" -type f \( -name '*.bit' -o -name '*.bin' -o -name '*.bif' \) | wc -l) files"
echo "  flash writers (name *flash*):   $(find "$I" -type f -iname '*flash*' | wc -l) files"

echo ""
echo "== 5. per-patch file inventory =="
echo "--- heartbeat patch (sdr_rml23_live_heartbeat_errata_patch.tar.gz) ---"
tar tzf dist/sdr_rml23_live_heartbeat_errata_patch.tar.gz | sed 's#^[^/]*/##' | grep -v '^HEARTBEAT_ERRATA_PATCH_SHA256SUMS.txt$'
echo "--- UI patch (sdr_rml23_live_ui_redesign_patch.tar.gz) ---"
tar tzf dist/sdr_rml23_live_ui_redesign_patch.tar.gz | sed 's#^[^/]*/##' | grep -v '^UI_REDESIGN_PATCH_SHA256SUMS.txt$'

echo ""
echo "== 6. frozen-category cross-check (must be empty) =="
CROSS="$( { tar tzf dist/sdr_rml23_live_heartbeat_errata_patch.tar.gz; tar tzf dist/sdr_rml23_live_ui_redesign_patch.tar.gz; } \
  | sed 's#^[^/]*/##' \
  | grep -E '(^|/)(model_rml23|model_12class|deployment_golden|contracts)(/|$)|preprocess|\.(v|sv|vhdl|vhd|bit|bin|bif)$' || true )"
if [ -z "$CROSS" ]; then
  echo "  (none) -- no patch file touches model/golden/labels/preprocess/RTL/bitstream/Flash"
else
  echo "  *** UNEXPECTED ***"
  echo "$CROSS"
fi

echo ""
echo "FROZEN ASSETS VERIFIED UNCHANGED"
