#!/usr/bin/env bash
# Gate 5: digital-loopback multi-tone -> NCO downconvert -> streaming resample ->
# 128 kHz / 1024-complex frames -> fixed receiver_scale / Q1.15.
# Usage: scripts/board_resampler_test.sh [--tone=<hz> --probe=<hz> --samples=<n>]
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/board_package/bin/board_resampler_test"
LOG="$ROOT/logs/board_resampler_test.log"
mkdir -p "$(dirname "$LOG")"

if [ ! -x "$BIN" ]; then
    echo "ERROR: $BIN not built. Run: board_package/build_on_board.sh" >&2
    exit 125
fi

echo "[$(date -u +%FT%TZ)] gate5 resampler_test $*" >>"$LOG"
"$BIN" "$@" 2>&1 | tee -a "$LOG"
exit "${PIPESTATUS[0]}"
