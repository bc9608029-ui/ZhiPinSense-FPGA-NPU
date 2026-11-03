#!/usr/bin/env bash
# Gate 2: RX-only acquisition (environment noise), save raw IQ for PC review.
# Usage: scripts/board_rx_only.sh [--center=<hz> --frames=<n> --out=<path>]
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/board_package/bin/board_rx_only"
LOG="$ROOT/logs/board_rx_only.log"
mkdir -p "$(dirname "$LOG")"

if [ ! -x "$BIN" ]; then
    echo "ERROR: $BIN not built. Run: board_package/build_on_board.sh" >&2
    exit 125
fi

echo "[$(date -u +%FT%TZ)] gate2 rx_only $*" >>"$LOG"
"$BIN" "$@" 2>&1 | tee -a "$LOG"
exit "${PIPESTATUS[0]}"
