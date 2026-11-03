#!/usr/bin/env bash
# stop_ui_live.sh -- stop the LIVE UI server started by run_ui_live.sh.
#
# Reads the PID file, verifies the process still exists AND that its cmdline names
# board_ui_live_12class (so a recycled PID can never be killed by mistake), sends
# SIGTERM, waits for exit, then removes the PID/sock state files and the socket
# node.  Deliberately does NOT use pkill/killall (a name match could hit an
# unrelated process).
set -euo pipefail

RUN_DIR="/tmp/sdr_ui_live"
PID_FILE="$RUN_DIR/ui_live.pid"
SOCK_FILE="$RUN_DIR/ui_live.sock"

if [ ! -f "$PID_FILE" ]; then
    echo "UI_LIVE_NOT_RUNNING (no pid file)" >&2
    exit 1
fi
PID="$(cat "$PID_FILE")"

if ! kill -0 "$PID" 2>/dev/null; then
    echo "UI_LIVE_NOT_RUNNING (pid $PID gone)" >&2
    rm -f "$PID_FILE" "$SOCK_FILE"
    exit 1
fi

# Refuse to signal any process whose cmdline does not name our server.
if ! grep -q 'board_ui_live_12class' "/proc/$PID/cmdline" 2>/dev/null; then
    echo "UI_LIVE_STOP_REFUSED pid=$PID (cmdline does not name board_ui_live_12class)" >&2
    exit 1
fi

kill -TERM "$PID"

i=0
while [ "$i" -lt 50 ]; do
    if ! kill -0 "$PID" 2>/dev/null; then break; fi
    i=$((i + 1))
    sleep 0.2
done

# Best-effort cleanup of the socket node (the server also unlinks it on exit).
SOCK="$(cat "$SOCK_FILE" 2>/dev/null || echo /run/sdr_amr_ui.sock)"
rm -f "$PID_FILE" "$SOCK_FILE" "$SOCK"

if kill -0 "$PID" 2>/dev/null; then
    echo "UI_LIVE_STOP_TIMEOUT pid=$PID (still running)" >&2
    exit 1
fi
echo "UI_LIVE_STOPPED pid=$PID"
