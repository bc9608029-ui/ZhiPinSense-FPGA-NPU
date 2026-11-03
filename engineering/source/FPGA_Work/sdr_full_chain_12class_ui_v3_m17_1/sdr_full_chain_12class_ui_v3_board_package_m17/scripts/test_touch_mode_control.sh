#!/usr/bin/env bash
# test_touch_mode_control.sh -- M16 board acceptance: third-page physical touch
# mode control (FIXED / AUTO LOCK / BAND SCAN / START / STOP).
#
# Prep / supervision / logging ONLY.  This script does NOT drive the touchscreen
# and does NOT use mode_ctl.sh to substitute manual touch: the acceptance evidence
# is the UI's own TOUCH_CONTROL_RESULT line, produced by REAL finger taps on the
# third (MODE) page.  The human performs the taps; this script only:
#
#   * verifies the prerequisites (UI binary built + UI log present);
#   * tails the UI log for UI_CTL / UI_CTL_TAP / TOUCH_CONTROL_STATS /
#     TOUCH_CONTROL_RESULT lines (supervision + logging);
#   * prints the final PASS/FAIL verdict straight from the UI's result line.
#
# Prereq (run in order, as root) -- M17.1 corrected order:
#   1. ./scripts/run_ui_live.sh          (board_ui_live_12class -> /tmp/sdr_ui_live/ui_live.log)
#   2. a LONG-RUNNING Gate 9 DIGITAL producer holding the control server on
#      /run/sdr_amr_control.sock:
#        ./scripts/run_gate9_ui.sh --phase=digital --rec-scale=<calibrated> --frames=<large>
#      (NOTE: --phase=offline is a ONE-SHOT golden replay that exits -- it is NOT a
#       long-running producer and MUST NOT be used for touch acceptance.)
#
# Recommended one-shot orchestration (UI first -> digital producer -> control sock
# -> this script), with rec_scale fail-closed:
#   ./scripts/run_m17_touch_acceptance.sh [--rec-scale=..] [--timeout=300]
#
# Then:  ./scripts/test_touch_mode_control.sh [--ui-log=...] [--control-sock=...] [--timeout=300]
#
# Exit 0 = TOUCH_CONTROL_RESULT result=PASS; non-zero otherwise.
set -euo pipefail
. "$(dirname "$0")/common.sh"

UI_LOG="/tmp/sdr_ui_live/ui_live.log"
CTL_SOCK="/run/sdr_amr_control.sock"
TIMEOUT="${TIMEOUT:-300}"
for a in "$@"; do
    case "$a" in
        --ui-log=*) UI_LOG="${a#--ui-log=}" ;;
        --control-sock=*) CTL_SOCK="${a#--control-sock=}" ;;
        --timeout=*) TIMEOUT="${a#--timeout=}" ;;
    esac
done

banner "M16: third-page physical touch mode control"

# ---- prep --------------------------------------------------------------------
require_bin board_ui_live_12class >/dev/null
[ -f "$UI_LOG" ] || {
    echo "TOUCH_CONTROL_PREP_FAIL: UI log not found ($UI_LOG)." >&2
    echo "   Start it first: ./scripts/run_ui_live.sh" >&2
    exit 2
}

SOCK="$CTL_SOCK"
if [ -S "$SOCK" ]; then
    echo "PREP control socket present: $SOCK"
else
    echo "PREP WARNING: control socket $SOCK not up -- the MODE-page buttons stay"
    echo "              inert until the LONG-RUNNING digital Gate 9 producer starts"
    echo "              its control server (see run_m17_touch_acceptance.sh)."
fi

# ---- supervision + logging ---------------------------------------------------
echo "TOUCH_CONTROL_WAIT timeout=${TIMEOUT}s log=$UI_LOG"
echo "   On the MODE page (third page), tap in order and watch each land:"
echo "     FIXED -> AUTO LOCK -> BAND SCAN -> FIXED, then STOP (freezes+STOPPED),"
echo "     START (RUNNING).  Each valid tap prints UI_CTL_TAP; convergence prints"
echo "     TOUCH_CONTROL_STATS and, at exit, TOUCH_CONTROL_RESULT."

# Tail the control lines live so the human sees each tap + ack land.
( tail -F "$UI_LOG" 2>/dev/null | grep --line-buffered -E 'UI_CTL|TOUCH_CONTROL' ) &
TAIL_PID=$!
trap 'kill "$TAIL_PID" 2>/dev/null || true' EXIT

RESULT=""
deadline=$(( $(date +%s) + TIMEOUT ))
while [ "$(date +%s)" -lt "$deadline" ]; do
    if grep -q 'TOUCH_CONTROL_RESULT' "$UI_LOG" 2>/dev/null; then
        RESULT="$(grep 'TOUCH_CONTROL_RESULT' "$UI_LOG" | tail -n 1)"
        break
    fi
    sleep 1
done

if [ -z "$RESULT" ]; then
    echo "TOUCH_CONTROL_RESULT result=FAIL reason=no_result_within_timeout" >&2
    exit 1
fi

echo "$RESULT"
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
