#!/usr/bin/env bash
# _task_b_delta.sh -- exact file-level delta of Task B (UI redesign) relative to
# the correctness-fix baseline (dist/sdr_rml23_live_board_package_correctness_fix).
# Prints the changed/new/removed paths only (dist/, artifacts/, dist_hist/ are
# packaging/output dirs and are ignored).
set -euo pipefail
ROOT=/mnt/f/FPGA_Work/sdr_rml24_npu_deployment_m29/board_rml23_live
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
tar -xzf "$ROOT/dist/sdr_rml23_live_board_package_correctness_fix.tar.gz" -C "$TMP"
BASE="$TMP/sdr_rml23_live_board_package_correctness_fix"

echo "=== Task B delta vs correctness-fix baseline (81d66586) ==="
diff -rq "$BASE" "$ROOT" 2>/dev/null \
  | grep -vE "Only in $ROOT/(dist|artifacts|dist_hist)(/|$)" \
  | grep -vE "Only in $ROOT/(dist|artifacts|dist_hist):" \
  || true
