#!/usr/bin/env bash
# Gate 3: digital loopback (loopback=1, no external RF).  TX CW tone, detect on RX.
# Usage: scripts/board_digital_loopback.sh [--center=<hz> --tone=<hz> --frames=<n>]
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/board_package/bin/board_digital_loopback"
LOG="$ROOT/logs/board_digital_loopback.log"
mkdir -p "$(dirname "$LOG")"

if [ ! -x "$BIN" ]; then
    echo "ERROR: $BIN not built. Run: board_package/build_on_board.sh" >&2
    exit 125
fi

echo "[$(date -u +%FT%TZ)] gate3 digital_loopback $*" >>"$LOG"
"$BIN" "$@" 2>&1 | tee -a "$LOG"
exit "${PIPESTATUS[0]}"
