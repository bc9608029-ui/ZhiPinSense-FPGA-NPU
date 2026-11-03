#!/usr/bin/env bash
# M29 Phase F4 — start the RML23-AMSSB-MERGED post-processing chain on the board.
#
# Runs the merge post-processor over a stream of raw 24-dim NPU logits and writes
# one JSONL result line per frame.  The NPU model is loaded once by the existing
# driver (NOT reopened per frame); this script only wraps the software merge.
#
#   ./scripts/start_rml23.sh <logits.f32> <n_frames> [out.jsonl]
#
#   logits.f32   raw 24-dim float32 logits, one frame = 24 little-endian floats
#   n_frames     number of frames to process (e.g. 1000, 10000)
#   out.jsonl    result log (default: result/rml23_result.jsonl)
#
# Fail-closed: refuses to start if the packaged model or contract SHA does not
# match the frozen deployment values.
set -euo pipefail

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PKG_DIR"

if [ "$#" -lt 2 ]; then
  echo "usage: $0 <logits.f32> <n_frames> [out.jsonl]" >&2
  exit 2
fi

LOGITS="$1"
N_FRAMES="$2"
OUT="${3:-result/rml23_result.jsonl}"

# fail-closed identity gate before any processing
"$PKG_DIR/scripts/verify_package.sh" >/dev/null || {
  echo "FAIL: package identity verification failed; refusing to start." >&2
  exit 1
}

if [ ! -f "$LOGITS" ]; then
  echo "FAIL: logits stream not found: $LOGITS" >&2
  exit 2
fi

if [ ! -x "$PKG_DIR/bin/rml23_merged_main" ]; then
  echo "FAIL: bin/rml23_merged_main not built; run scripts/build_board.sh first." >&2
  exit 1
fi

mkdir -p result
PIDFILE="result/rml23_merged.pid"

if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then
  echo "rml23_merged already running (pid $(cat "$PIDFILE")); stop it first." >&2
  exit 1
fi

echo "[start_rml23] processing $N_FRAMES frames from $LOGITS -> $OUT"
"$PKG_DIR/bin/rml23_merged_main" "$LOGITS" "$N_FRAMES" > "$OUT" &
PID=$!
echo "$PID" > "$PIDFILE"
echo "[start_rml23] started pid=$PID result=$OUT"
