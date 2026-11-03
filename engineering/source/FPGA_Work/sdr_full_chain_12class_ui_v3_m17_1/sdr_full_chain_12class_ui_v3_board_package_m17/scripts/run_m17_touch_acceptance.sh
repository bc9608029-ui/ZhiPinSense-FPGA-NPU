#!/usr/bin/env bash
# run_m17_touch_acceptance.sh -- M17.1 corrected board touch acceptance orchestration.
#
# One-shot, ordered orchestration for the third-page (MODE) physical-touch
# acceptance.  It fixes the two M17 acceptance-flow errata:
#   * the touch producer MUST be a LONG-RUNNING digital producer, NOT
#     `run_gate9_ui.sh --phase=offline` (offline replays finite golden samples
#     and exits -- it is never a long-running producer);
#   * the start order MUST be UI-first: UI -> wait UI socket -> long-running
#     digital producer -> wait control socket -> touch acceptance.
#
# This script ONLY starts/stops processes and supervises.  It does NOT drive the
# touchscreen and does NOT use mode_ctl.sh to substitute manual touch: the human
# performs the taps, and the verdict comes from the UI's own TOUCH_CONTROL_RESULT
# line (via scripts/test_touch_mode_control.sh).
#
# 14 consistency-checked behaviors (verified by scripts/test_m17_touch_acceptance.sh):
#   [1]  UI-first ordering: start UI (run_ui_live.sh) before the producer.
#   [2]  UI readiness wait: block for the UI data socket / UI_LIVE_READY (fail-closed).
#   [3]  Digital producer: launch --phase=digital (offline is rejected, never used).
#   [4]  Producer-after-UI: the producer is started only after UI readiness.
#   [5]  Control-socket wait: block for the producer's control socket (fail-closed).
#   [6]  rec_scale.txt resolution: current dir first, then package root; fail-closed
#        if absent (prompts to calibrate).
#   [7]  --rec-scale override: an explicit --rec-scale=<value> wins over rec_scale.txt.
#   [8]  rec_scale.txt format: parse exactly `rec_scale=<value>`; reject malformed /
#        non-positive / zero (never silently fall back to 1.0).
#   [9]  rec_scale forwarding: the resolved --rec-scale=<value> is passed to the producer.
#  [10]  --producer-frames override: forwarded to the producer (default: large,
#        effectively continuous for the acceptance window).
#  [11]  --ui-sock / --control-sock override: custom sockets forwarded (defaults
#        /run/sdr_amr_ui.sock and /run/sdr_amr_control.sock).
#  [12]  --timeout override: wait + acceptance timeout honored (default 300s).
#  [13]  Log directory: all orchestration logs under /tmp/m17_touch_acceptance/.
#  [14]  Verdict delegation: final `M17_TOUCH_ACCEPTANCE result=PASS|FAIL` is derived
#        from test_touch_mode_control.sh's TOUCH_CONTROL_RESULT (PASS iff
#        commands_sent>0 && applied==sent && rejected==0 && timeout==0 && duplicate==0).
#
# Usage (as root):
#   ./scripts/run_m17_touch_acceptance.sh [--rec-scale=1.234] [--producer-frames=1000000000]
#       [--ui-sock=/run/sdr_amr_ui.sock] [--control-sock=/run/sdr_amr_control.sock]
#       [--timeout=300]
#
# Exit: 0 = M17_TOUCH_ACCEPTANCE result=PASS; non-zero otherwise.
#
# Sourcing guard: `RUN_M17_TOUCH_ACCEPTANCE_LIB=1 . scripts/run_m17_touch_acceptance.sh`
# defines the pure helpers (parse_rec_scale_file, resolve_rec_scale) and returns
# without executing main -- used by scripts/test_m17_touch_acceptance.sh.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/common.sh"

# ---- defaults ----------------------------------------------------------------
UI_SOCK="/run/sdr_amr_ui.sock"
CTL_SOCK="/run/sdr_amr_control.sock"
TIMEOUT=300
PRODUCER_FRAMES=1000000000
REC_SCALE_OVERRIDE=""
LOG_DIR="/tmp/m17_touch_acceptance"

# parse_rec_scale_file <path> -> prints the numeric value on stdout, returns 0.
# Fail-closed (returns non-zero, nothing meaningful on stdout) if the file is
# missing or does not contain exactly one well-formed `rec_scale=<value>` line.
parse_rec_scale_file() {
    local f="$1" val
    if [ ! -f "$f" ]; then
        echo "parse_rec_scale_file: not found: $f" >&2
        return 1
    fi
    val="$(grep -E '^rec_scale=[[:space:]]*[0-9]+([.][0-9]+)?([eE][+-]?[0-9]+)?[[:space:]]*$' "$f" \
             | tail -n 1 | sed -E 's/^rec_scale=[[:space:]]*//; s/[[:space:]]*$//' || true)"
    if [ -z "$val" ]; then
        echo "parse_rec_scale_file: malformed (expected a single 'rec_scale=<value>' line): $f" >&2
        return 1
    fi
    # Strictly positive finite number (rejects 0 / negative / NaN / inf).
    awk -v v="$val" 'BEGIN{ exit (v ~ /^[0-9]+([.][0-9]+)?([eE][+-]?[0-9]+)?$/ && (v+0) > 0) ? 0 : 1 }' \
        || { echo "parse_rec_scale_file: invalid value '$val' in $f" >&2; return 1; }
    printf '%s\n' "$val"
    return 0
}

# resolve_rec_scale -> prints the rec_scale to use on stdout, returns 0.
# [6] current-dir-first, then package root; [7] explicit override wins; [8] never 1.0.
resolve_rec_scale() {
    if [ -n "$REC_SCALE_OVERRIDE" ]; then
        awk -v v="$REC_SCALE_OVERRIDE" 'BEGIN{ exit (v ~ /^[0-9]+([.][0-9]+)?([eE][+-]?[0-9]+)?$/ && (v+0) > 0) ? 0 : 1 }' \
            || { echo "M17_TOUCH_ACCEPTANCE_PREP_FAIL: --rec-scale value invalid: '$REC_SCALE_OVERRIDE'" >&2; return 2; }
        printf '%s\n' "$REC_SCALE_OVERRIDE"
        return 0
    fi
    if [ -f "./rec_scale.txt" ]; then
        parse_rec_scale_file "./rec_scale.txt" || return 2
        return 0
    fi
    if [ -f "$ROOT/rec_scale.txt" ]; then
        parse_rec_scale_file "$ROOT/rec_scale.txt" || return 2
        return 0
    fi
    echo "M17_TOUCH_ACCEPTANCE_PREP_FAIL: rec_scale.txt not found (current dir or package root)." >&2
    echo "  Calibrate first:  ./scripts/run_calibrate_rec_scale.sh" >&2
    echo "  (writes rec_scale.txt into the package root), or pass --rec-scale=<value>." >&2
    return 2
}

# wait_for_socket <sock> <label> -> returns 0 when the socket node exists.
wait_for_socket() {
    local sock="$1" label="$2" deadline
    deadline=$(( $(date +%s) + TIMEOUT ))
    while [ "$(date +%s)" -lt "$deadline" ]; do
        [ -S "$sock" ] && return 0
        sleep 1
    done
    echo "M17_TOUCH_ACCEPTANCE_PREP_FAIL: $label socket not up within ${TIMEOUT}s: $sock" >&2
    return 1
}

# _cleanup: best-effort stop the background producer on exit.
_cleanup() {
    if [ -n "${PRODUCER_PID:-}" ] && kill -0 "$PRODUCER_PID" 2>/dev/null; then
        kill "$PRODUCER_PID" 2>/dev/null || true
        wait "$PRODUCER_PID" 2>/dev/null || true
    fi
}

main() {
    mkdir -p "$LOG_DIR"
    REC_SCALE="$(resolve_rec_scale)" || exit 2
    trap _cleanup EXIT

    banner "M17.1 touch acceptance (UI -> digital producer -> touch)"

    # [1][2] start UI first, then block for its data socket (fail-closed).
    echo "M17_TOUCH_ACCEPTANCE_STEP start_ui sock=$UI_SOCK"
    if [ -S "$UI_SOCK" ]; then
        echo "  UI socket already present: $UI_SOCK"
    else
        "$ROOT/scripts/run_ui_live.sh" --sock="$UI_SOCK" >"$LOG_DIR/ui_live.log" 2>&1 \
            || { echo "M17_TOUCH_ACCEPTANCE_PREP_FAIL: UI server failed to start" >&2; exit 2; }
    fi
    wait_for_socket "$UI_SOCK" "UI (data)" || exit 2

    # [3][4][9][10] start the LONG-RUNNING digital producer (never offline), after UI.
    echo "M17_TOUCH_ACCEPTANCE_STEP start_producer phase=digital frames=$PRODUCER_FRAMES rec_scale=$REC_SCALE"
    "$ROOT/scripts/run_gate9_ui.sh" \
        --phase=digital \
        --frames="$PRODUCER_FRAMES" \
        --rec-scale="$REC_SCALE" \
        --ctl-sock="$CTL_SOCK" \
        --sock="$UI_SOCK" \
        >"$LOG_DIR/gate9_digital.log" 2>&1 &
    PRODUCER_PID=$!

    # [5] block for the producer's control socket (fail-closed).
    if ! wait_for_socket "$CTL_SOCK" "Gate 9 control"; then
        echo "  producer log tail:" >&2
        tail -n 20 "$LOG_DIR/gate9_digital.log" >&2 || true
        exit 2
    fi

    # [13][14] delegate the human-touch acceptance; verdict flows through.
    echo "M17_TOUCH_ACCEPTANCE_STEP run_touch_acceptance timeout=${TIMEOUT}s"
    set +e
    "$ROOT/scripts/test_touch_mode_control.sh" \
        --control-sock="$CTL_SOCK" \
        --timeout="$TIMEOUT"
    RC=$?
    set -e

    if [ "$RC" -eq 0 ]; then
        echo "M17_TOUCH_ACCEPTANCE result=PASS"
    else
        echo "M17_TOUCH_ACCEPTANCE result=FAIL (test_touch_mode_control exit=$RC)"
    fi
    return "$RC"
}

if [ "${RUN_M17_TOUCH_ACCEPTANCE_LIB:-0}" = "1" ]; then
    # Sourced as a library: define helpers only, do not execute main.
    return 0 2>/dev/null || exit 0
fi

# ---- arg parsing (must stay after the library guard so sourced mode is cheap) --
for a in "$@"; do
    case "$a" in
        --rec-scale=*) REC_SCALE_OVERRIDE="${a#--rec-scale=}" ;;
        --producer-frames=*) PRODUCER_FRAMES="${a#--producer-frames=}" ;;
        --ui-sock=*) UI_SOCK="${a#--ui-sock=}" ;;
        --control-sock=*) CTL_SOCK="${a#--control-sock=}" ;;
        --timeout=*) TIMEOUT="${a#--timeout=}" ;;
        *) echo "run_m17_touch_acceptance.sh: unknown option: $a" >&2; exit 2 ;;
    esac
done

main
