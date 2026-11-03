#!/usr/bin/env bash
# stop_all_rml23.sh -- stop the RML23 23-class LIVE chain started by
# start_all_rml23.sh (producer first, then the UI server).
#
# Reads the PID files written by start_all_rml23.sh, verifies each PID is still
# alive AND that its executable is exactly the RML23 binary, sends SIGTERM, waits
# for exit, then removes the state files and the two socket nodes.  Deliberately
# does NOT use pkill/killall, and never signals a stale/reused PID or a 12-class
# process.  The producer is stopped first so its device state is restored cleanly
# before the UI server is torn down.
#
#   ./scripts/stop_all_rml23.sh [--run-dir=/path]   # default /tmp/sdr_rml23_live
#
# Exit: 0 = both stopped (or already gone); 1 = nothing was running to stop.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/common_rml23.sh"
. "$SCRIPT_DIR/process_guard.sh"

RUN_DIR="${RML23_LIVE_RUN_DIR:-/tmp/sdr_rml23_live}"
for _a in "$@"; do
    case "$_a" in
        --run-dir=*) RUN_DIR="${_a#--run-dir=}" ;;
        *) echo "stop_all_rml23.sh: unknown option '$_a'" >&2; exit 2 ;;
    esac
done

UI_PID_FILE="$RUN_DIR/ui_live_rml23.pid"
PROD_PID_FILE="$RUN_DIR/producer_rml23.pid"

# Resolve the binary paths WITHOUT require_bin's exit-on-missing, so a removed
# binary never blocks a clean shutdown.  These are the exact paths start_all used
# (via require_bin -> $BIN_DIR/<name>), so /proc/<pid>/exe matches them.
BIN_DIR="${BIN_DIR:-$ROOT/bin}"
UI_BIN="$BIN_DIR/board_ui_live_rml23"
PROD_BIN="$BIN_DIR/board_gate9_full_chain_rml23"

stopped=0

# ---- stop the producer first (restores device state) -----------------------
if [ -f "$PROD_PID_FILE" ]; then
    PROD_PID="$(cat "$PROD_PID_FILE")"
    if pid_matches_bin "$PROD_PID" "$PROD_BIN"; then
        stop_pid "$PROD_PID"
        echo "PRODUCER_STOPPED pid=$PROD_PID"
        stopped=1
    else
        echo "PRODUCER_NOT_RUNNING (pid $PROD_PID gone or not $PROD_BIN)" >&2
    fi
    rm -f "$PROD_PID_FILE"
fi

# ---- stop the UI server ----------------------------------------------------
if [ -f "$UI_PID_FILE" ]; then
    UI_PID="$(cat "$UI_PID_FILE")"
    if pid_matches_bin "$UI_PID" "$UI_BIN"; then
        stop_pid "$UI_PID"
        echo "UI_STOPPED pid=$UI_PID"
        stopped=1
    else
        echo "UI_NOT_RUNNING (pid $UI_PID gone or not $UI_BIN)" >&2
    fi
    rm -f "$UI_PID_FILE"
fi

# ---- best-effort socket-node cleanup ---------------------------------------
# The producer unlinks CTL_SOCK and the server unlinks UI_SOCK on exit; this is a
# second layer against a stale node left by a killed process.  Never touches the
# 12-class sockets (/run/sdr_amr_ui.sock, /run/sdr_amr_control.sock).
rm -f "$UI_SOCK" "$CTL_SOCK"

if [ "$stopped" = "0" ]; then
    echo "STOP_ALL_NOTHING_RUNNING (no live RML23 children found)" >&2
    exit 1
fi
echo "STOP_ALL_DONE ui_sock=$UI_SOCK ctl_sock=$CTL_SOCK"
exit 0
