#!/usr/bin/env bash
# M29 Phase F4 — stop the RML23-AMSSB-MERGED post-processing chain on the board.
#
#   ./scripts/stop_rml23.sh
#
# Terminates the process recorded in result/rml23_merged.pid and removes the
# stale pidfile.  Safe to call when nothing is running.
set -euo pipefail

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PKG_DIR"

PIDFILE="result/rml23_merged.pid"

if [ ! -f "$PIDFILE" ]; then
  echo "[stop_rml23] no pidfile; nothing to stop."
  exit 0
fi

PID="$(cat "$PIDFILE")"
if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
  kill "$PID"
  # wait briefly for it to exit, then force if needed
  for _ in $(seq 1 20); do
    kill -0 "$PID" 2>/dev/null || break
    sleep 0.1
  done
  if kill -0 "$PID" 2>/dev/null; then
    kill -9 "$PID" 2>/dev/null || true
  fi
  echo "[stop_rml23] stopped pid=$PID"
else
  echo "[stop_rml23] pid=$PID not running (stale pidfile)."
fi

rm -f "$PIDFILE"
