#!/usr/bin/env bash
# M29 Phase F4 — 10000-frame stability test.
#
#   ./scripts/test_10000_frames.sh <logits.f32>
#
# Runs the merge chain over 10000 frames and validates the result log, then
# re-runs the merge and confirms bit-for-bit determinism (the merge is
# stateless).  Exit 0 only if package identity, all 10000 result lines, and the
# determinism check all pass.
set -euo pipefail

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PKG_DIR"

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <logits.f32>" >&2
  exit 2
fi

LOGITS="$1"
OUT1="result/rml23_result_10000_run1.jsonl"
OUT2="result/rml23_result_10000_run2.jsonl"

run_once() {
  local out="$1"
  "$PKG_DIR/scripts/start_rml23.sh" "$LOGITS" 10000 "$out"
  local pidfile="result/rml23_merged.pid"
  if [ -f "$pidfile" ]; then
    local pid="$(cat "$pidfile")"
    while kill -0 "$pid" 2>/dev/null; do sleep 0.1; done
  fi
}

echo "[test_10000] run 1 ..."
run_once "$OUT1"
echo "[test_10000] run 2 (determinism) ..."
run_once "$OUT2"

echo "[test_10000] validating run 1 ..."
"$PKG_DIR/scripts/check_ui_result.sh" "$OUT1" 10000
echo "[test_10000] validating run 2 ..."
"$PKG_DIR/scripts/check_ui_result.sh" "$OUT2" 10000

if cmp -s "$OUT1" "$OUT2"; then
  echo "[test_10000] deterministic: run1 == run2"
else
  echo "FAIL: merge is not deterministic (run1 != run2)" >&2
  exit 1
fi

echo "== 10000-FRAME STABILITY TEST PASSED =="
