#!/usr/bin/env bash
# test_touch_mode_control.sh -- M16/M17.2 board acceptance: third-page physical touch
# mode control (FIXED / AUTO LOCK / BAND SCAN / START / STOP).
#
# Prep / supervision / logging ONLY.  This script does NOT drive the touchscreen
# and does NOT use mode_ctl.sh to substitute manual touch: the acceptance evidence
# is the UI's own TOUCH_CONTROL_RESULT line, produced by REAL finger taps on the
# third (MODE) page.  The human performs the taps; this script only:
#
#   * verifies the prerequisites (UI binary built + UI log present + control
#     socket actually SERVED by a live process -- fail-closed [M17.2 #6]);
#   * tails the UI log (from this run's byte offset onward) for UI_CTL /
#     UI_CTL_TAP / TOUCH_CONTROL_STATS / TOUCH_CONTROL_RESULT lines;
#   * accepts ONLY a TOUCH_CONTROL_RESULT appended AFTER the recorded log offset,
#     so an old result from a previous run can never produce a false PASS
#     [M17.2 #4];
#   * prints the final PASS/FAIL verdict straight from the UI's result line.
#
# Prereq (run in order, as root) -- M17.2 corrected order:
#   1. ./scripts/run_ui_live.sh --ctl-sock=<control-sock>   (UI server + control client)
#   2. a LONG-RUNNING Gate 9 DIGITAL producer holding the control server:
#        ./scripts/run_gate9_ui.sh --phase=digital --rec-scale=<calibrated> \
#            --frames=<finite> --ctl-sock=<control-sock>
#      (NOTE: --phase=offline is a ONE-SHOT golden replay that exits -- it is NOT a
#       long-running producer and MUST NOT be used for touch acceptance.)
#
# Recommended one-shot orchestration (stop stale -> UI -> digital producer -> touch):
#   ./scripts/run_m17_touch_acceptance.sh [--rec-scale=..] [--timeout=300]
#
# Standalone (advanced):  ./scripts/test_touch_mode_control.sh \
#     [--ui-log=...] [--control-sock=...] [--timeout=300] [--log-offset=0] [--run-id=...]
#
# Exit 0 = TOUCH_CONTROL_RESULT result=PASS; non-zero otherwise.
set -euo pipefail
. "$(dirname "$0")/common.sh"
. "$(dirname "$0")/process_guard.sh"

UI_LOG="/tmp/sdr_ui_live/ui_live.log"
CTL_SOCK="/run/sdr_amr_control.sock"
TIMEOUT="${TIMEOUT:-300}"
LOG_OFFSET="0"
RUN_ID=""

for a in "$@"; do
    case "$a" in
        --ui-log=*) UI_LOG="${a#--ui-log=}" ;;
        --control-sock=*) CTL_SOCK="${a#--control-sock=}" ;;
        --timeout=*) TIMEOUT="${a#--timeout=}" ;;
        --log-offset=*) LOG_OFFSET="${a#--log-offset=}" ;;
        --run-id=*) RUN_ID="${a#--run-id=}" ;;
        *) echo "test_touch_mode_control.sh: unknown option: $a" >&2; exit 2 ;;
    esac
done

# await_result -> prints the NEWEST TOUCH_CONTROL_RESULT appended after LOG_OFFSET,
# or returns non-zero on timeout.  Only post-offset content is ever considered.
await_result() {
    local out deadline
    deadline=$(( $(date +%s) + TIMEOUT ))
    while [ "$(date +%s)" -lt "$deadline" ]; do
        out="$(tail_since "$UI_LOG" "$LOG_OFFSET" | grep 'TOUCH_CONTROL_RESULT' | tail -n 1)"
        if [ -n "$out" ]; then
            printf '%s\n' "$out"
            return 0
        fi
        sleep 1
    done
    return 1
}

# Sourcing guard: define await_result + parse args, do not run main.
if [ "${TOUCH_CONTROL_LIB:-0}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi

banner "M16/M17.2: third-page physical touch mode control"
[ -n "$RUN_ID" ] && echo "TOUCH_CONTROL_RUN run_id=$RUN_ID"
echo "TOUCH_CONTROL_LOG log=$UI_LOG offset=$LOG_OFFSET"

# ---- prep --------------------------------------------------------------------
require_bin board_ui_live_12class >/dev/null
[ -f "$UI_LOG" ] || {
    echo "TOUCH_CONTROL_PREP_FAIL: UI log not found ($UI_LOG)." >&2
    echo "   Start it first: ./scripts/run_ui_live.sh" >&2
    exit 2
}

# [M17.2 #6] fail-closed: the control socket must be SERVED by a live process.  A
# stale node left by a dead producer passes `-S` but is NOT listed in
# /proc/net/unix, so it is rejected here.
if socket_served "$CTL_SOCK"; then
    echo "PREP control socket served: $CTL_SOCK"
else
    echo "TOUCH_CONTROL_PREP_FAIL: control socket not served: $CTL_SOCK" >&2
    echo "  (a stale node is NOT a served socket.)  The MODE-page buttons stay inert" >&2
    echo "  until the LONG-RUNNING digital Gate 9 producer starts its control server." >&2
    echo "  Use ./scripts/run_m17_touch_acceptance.sh to orchestrate this correctly." >&2
    exit 2
fi

# ---- supervision + logging ---------------------------------------------------
echo "TOUCH_CONTROL_WAIT timeout=${TIMEOUT}s log=$UI_LOG offset=$LOG_OFFSET"
echo "   On the MODE page (third page), tap in order and watch each land:"
echo "     FIXED -> AUTO LOCK -> BAND SCAN -> FIXED, then STOP (freezes+STOPPED),"
echo "     START (RUNNING).  Each valid tap prints UI_CTL_TAP; convergence prints"
echo "     TOUCH_CONTROL_STATS and, at exit, TOUCH_CONTROL_RESULT."

# Tail the control lines live so the human sees each tap + ack land.  Only show
# lines from this run forward (tail -n 0 -F), so old-run lines are not replayed.
( tail -n 0 -F "$UI_LOG" 2>/dev/null | grep --line-buffered -E 'UI_CTL|TOUCH_CONTROL' ) &
TAIL_PID=$!
trap 'kill "$TAIL_PID" 2>/dev/null || true' EXIT

if RESULT="$(await_result)"; then
    echo "$RESULT"
else
    echo "TOUCH_CONTROL_RESULT result=FAIL reason=no_result_within_timeout" >&2
    exit 1
fi

case "$RESULT" in
    *"result=PASS"*)
        echo "TOUCH_MODE_CONTROL_ACCEPTED"
        exit 0
        ;;
    *)
        echo "TOUCH_MODE_CONTROL_REJECTED" >&2
        exit 1
        ;;
esac
