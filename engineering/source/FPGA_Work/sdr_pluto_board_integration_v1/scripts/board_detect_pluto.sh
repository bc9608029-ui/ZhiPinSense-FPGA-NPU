#!/usr/bin/env bash
# Gate 1: enumerate + open the Pluto (identity read-back).
# Usage: scripts/board_detect_pluto.sh [--uri=<iio_uri>]
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/board_package/bin/board_detect_pluto"
LOG="$ROOT/logs/board_detect_pluto.log"
mkdir -p "$(dirname "$LOG")"

if [ ! -x "$BIN" ]; then
    echo "ERROR: $BIN not built. Run: board_package/build_on_board.sh" >&2
    exit 125
fi

echo "[$(date -u +%FT%TZ)] gate1 detect_pluto $*" >>"$LOG"
"$BIN" "$@" 2>&1 | tee -a "$LOG"
exit "${PIPESTATUS[0]}"
