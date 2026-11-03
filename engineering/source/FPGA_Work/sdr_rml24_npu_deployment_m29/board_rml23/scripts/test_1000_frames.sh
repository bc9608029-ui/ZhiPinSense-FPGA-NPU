#!/usr/bin/env bash
# M29 Phase F4 — 1000-frame board test.
#
#   ./scripts/test_1000_frames.sh <logits.f32>
#
# Runs the merge chain over the first 1000 frames of a raw 24-dim logits stream
# and validates the result log.  Exit 0 only if the package identity is verified
# and all 1000 result lines pass the UI/result check.
set -euo pipefail

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PKG_DIR"

if [ "$#" -lt 1 ]; then
  echo "usage: $0 <logits.f32>" >&2
  exit 2
fi

LOGITS="$1"
OUT="result/rml23_result_1000.jsonl"

echo "[test_1000] running 1000-frame merge ..."
"$PKG_DIR/scripts/start_rml23.sh" "$LOGITS" 1000 "$OUT"

# start_rml23 runs in the background; wait for the pid to exit
PIDFILE="result/rml23_merged.pid"
if [ -f "$PIDFILE" ]; then
  PID="$(cat "$PIDFILE")"
  while kill -0 "$PID" 2>/dev/null; do sleep 0.1; done
fi

echo "[test_1000] validating result log ..."
"$PKG_DIR/scripts/check_ui_result.sh" "$OUT" 1000

echo "== 1000-FRAME TEST PASSED =="
