#!/usr/bin/env bash
# Gate 4: EXTERNAL RF loopback (loopback=0) -- EMITS RF from the TX antenna port.
#
# DISABLED by default: the binary refuses to run unless --confirm-safe-rf-path is
# passed.  Only run this with an antenna/cable/attenuator path you have verified,
# and only because you explicitly chose to.
#
# Usage: scripts/board_rf_loopback.sh --confirm-safe-rf-path [--center=<hz> ...]
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BIN="$ROOT/board_package/bin/board_rf_loopback"
LOG="$ROOT/logs/board_rf_loopback.log"
mkdir -p "$(dirname "$LOG")"

if [ ! -x "$BIN" ]; then
    echo "ERROR: $BIN not built. Run: board_package/build_on_board.sh" >&2
    exit 125
fi

echo "[$(date -u +%FT%TZ)] gate4 rf_loopback $*" >>"$LOG"
"$BIN" "$@" 2>&1 | tee -a "$LOG"
exit "${PIPESTATUS[0]}"
