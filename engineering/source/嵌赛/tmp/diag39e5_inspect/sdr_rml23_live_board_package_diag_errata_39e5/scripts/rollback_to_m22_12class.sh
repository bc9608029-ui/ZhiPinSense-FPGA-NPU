#!/usr/bin/env bash
# rollback_to_m22_12class.sh -- tear down the RML23 (M29 F5) live chain and leave
# the board ready to return to the M22.1 twelve-class chain.
#
# F5 is delivered as a SEPARATE directory (board_rml23_live); it never overwrites
# the M22/M23/M24 twelve-class deliverables.  "Rollback" therefore means:
#
#   1. stop the RML23 LIVE UI server (board_ui_live_rml23) if running;
#   2. stop any RML23 producer (board_gate9_full_chain_rml23) still running;
#   3. remove the RML23 UI socket / control socket / run-dir state so no stale
#      node or PID file can masquerade as a live RML23 chain;
#   4. confirm NO RML23 process or socket remains.
#
# It deliberately does NOT touch Flash, the bitstream, or the M22.1 twelve-class
# directory (the twelve-class chain is unaffected and remains the prior default).
#
# Exit: 0 = ROLLBACK_TO_M22_12CLASS result=PASS; 1 = FAIL (a residual remains).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/common_rml23.sh"
. "$SCRIPT_DIR/process_guard.sh"

RUN_DIR="${UI_RUN_DIR:-/tmp/sdr_ui_live_rml23}"

echo "ROLLBACK_TO_M22_12CLASS_STEP stop_ui_server"
if [ -f "$RUN_DIR/ui_live_rml23.pid" ]; then
    "$SCRIPT_DIR/stop_live_rml23.sh" >/dev/null 2>&1 || true
fi

echo "ROLLBACK_TO_M22_12CLASS_STEP stop_producers"
stopped=0
for p in $(find_pids_named board_gate9_full_chain_rml23); do
    stop_pid "$p" || true
    stopped=$((stopped + 1))
done

echo "ROLLBACK_TO_M22_12CLASS_STEP cleanup_state"
rm -f "$RUN_DIR/ui_live_rml23.pid" \
      "$RUN_DIR/ui_live_rml23.sock" \
      "$RUN_DIR/ui_live_rml23.log" 2>/dev/null || true
rm -f "$UI_SOCK" "$CTL_SOCK" 2>/dev/null || true

# Fail-closed: assert no residual RML23 process or served socket remains.
residual=0
pids="$(find_pids_named board_gate9_full_chain_rml23; find_pids_named board_ui_live_rml23)"
if [ -n "$pids" ]; then residual=1; fi
if socket_served "$UI_SOCK"; then residual=1; fi

if [ "$residual" -eq 0 ]; then
    echo "ROLLBACK_TO_M22_12CLASS result=PASS stopped_producers=$stopped"
    echo "  The M22.1 twelve-class chain is unaffected and remains the prior default."
    exit 0
fi
echo "ROLLBACK_TO_M22_12CLASS result=FAIL residual_pids='$pids'" >&2
exit 1
