#!/usr/bin/env bash
# run_ui_live.sh -- start the twelve-class LIVE UI server (board_ui_live_12class)
# in the background.
#
#   ./run_ui_live.sh [--sock=/path] [--stale-ms=5000] [--model-sha=<sha>]
#
# Writes the PID to /tmp/sdr_ui_live/ui_live.pid, the socket path to
# /tmp/sdr_ui_live/ui_live.sock, and stdout+stderr to
# /tmp/sdr_ui_live/ui_live.log.  Polls until the socket node exists AND the log
# shows UI_LIVE_READY, then echoes that line.  Fail-closed (exit 1) if the socket
# never appears or the process dies.
#
# The server needs root to map /dev/mem + /dev/udmabuf0 (run as root).
set -euo pipefail
. "$(dirname "$0")/common.sh"

BIN="$(require_bin board_ui_live_12class)"
RUN_DIR="/tmp/sdr_ui_live"
PID_FILE="$RUN_DIR/ui_live.pid"
SOCK_FILE="$RUN_DIR/ui_live.sock"
LOG_FILE="$RUN_DIR/ui_live.log"
mkdir -p "$RUN_DIR"

# Default socket; a --sock=... in the args overrides it (the binary's get_opt
# resolves later-occurrence-wins, and we mirror that here for the poll).
SOCK="/run/sdr_amr_ui.sock"
for a in "$@"; do
    case "$a" in
        --sock=*) SOCK="${a#--sock=}" ;;
    esac
done

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "UI_LIVE_ALREADY_RUNNING pid=$(cat "$PID_FILE")" >&2
    exit 1
fi

# Start detached; the server prints UI_LIVE_READY after bind/listen, then opens the
# HDMI framebuffer (version gate) and renders.  [M18] stdin is /dev/null and
# stdout+stderr go to the LOG FILE only, so the UI subprocess NEVER inherits the
# control serial console -- the terminal sees at most the single UI_LIVE_READY
# echoed below, never the server's periodic stats/connected lines.
nohup "$BIN" --sock="$SOCK" "$@" >"$LOG_FILE" 2>&1 </dev/null &
PID=$!
echo "$PID" > "$PID_FILE"
echo "$SOCK" > "$SOCK_FILE"

i=0
while [ "$i" -lt 100 ]; do
    if [ -S "$SOCK" ] && grep -q 'UI_LIVE_READY' "$LOG_FILE" 2>/dev/null; then
        echo "UI_LIVE_READY sock=$SOCK pid=$PID log=$LOG_FILE"
        exit 0
    fi
    if ! kill -0 "$PID" 2>/dev/null; then
        echo "UI_LIVE_FAIL socket_not_ready (server exited; see $LOG_FILE)" >&2
        rm -f "$PID_FILE" "$SOCK_FILE"
        exit 1
    fi
    i=$((i + 1))
    sleep 0.2
done

echo "UI_LIVE_FAIL socket_not_ready (timeout; see $LOG_FILE)" >&2
exit 1
