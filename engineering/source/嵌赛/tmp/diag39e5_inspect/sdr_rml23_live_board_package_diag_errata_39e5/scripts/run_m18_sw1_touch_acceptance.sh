#!/usr/bin/env bash
# run_m18_sw1_touch_acceptance.sh -- M18-SW1 Task C: single-verdict touch acceptance.
#
# Eliminates the same-round FAIL-then-PASS race that the M17 flow had: the M17
# touch test tailed the UI log for TOUCH_CONTROL_RESULT WHILE the UI was still
# running, but the UI only emits that line on process EXIT -- so the tail timed
# out, printed result=FAIL, then _cleanup stopped the UI, whose exit block emitted
# the real TOUCH_CONTROL_RESULT result=PASS a moment later.  The acceptance printed
# a FAIL and then a PASS for the SAME round.
#
# Corrected flow (one verdict, one line, no race):
#
#   (1)  stop + confirm no stale UI / Gate9 producer;
#   (2)  start THIS round's UI and verify its PID identity + data-socket ownership;
#   (3)  start THIS round's long-running digital producer and verify its PID
#        identity + control-socket ownership;
#   (4)  record the UI log byte-offset (AFTER the fresh UI is up -- the log is
#        truncated at startup) and mint a unique run_id;
#   (5)  the human performs the touch sequence on the MODE page;
#   (6)(7) the human confirms done by typing FINALIZE_TEST (explicit token);
#   (8)  the UI is stopped FIRST (SIGTERM -> g_stop_requested -> the normal exit
#        block emits the SINGLE TOUCH_CONTROL_RESULT line);
#   (9)  that single result is read back, gated by BOTH the post-offset tail AND
#        run_id=<this run>;
#   (10) the producer is stopped;
#   (11) EXACTLY ONE line `M18_SW1_TOUCH_ACCEPTANCE result=PASS|FAIL run_id=...`
#        is printed.  There is no second verdict: a late event cannot re-open the
#        verdict because the UI is already dead and the log is read once.
#
# Fail-closed aborts (no verdict, non-zero exit) on: UI-start-fail, Gate9-start-
# fail, socket-missing/wrong-owner, user-Ctrl-C, Gate9-early-exit, UI-early-exit,
# FINALIZE_TEST timeout, stale-log, stale-socket, PID-reuse.  A PASS that belongs
# to a different run_id is rejected by the run_id gate.  Cleanup only signals
# PIDs that are still alive AND still the same executable this run started.
#
# This script only starts/stops processes and supervises; it does NOT drive the
# touchscreen and does NOT substitute manual touch.  The human performs the taps;
# the verdict comes from the UI's own TOUCH_CONTROL_RESULT line.
#
# Usage (as root):
#   ./scripts/run_m18_sw1_touch_acceptance.sh [--rec-scale=1.234]
#       [--producer-frames=50000] [--ui-sock=/run/sdr_amr_ui.sock]
#       [--control-sock=/run/sdr_amr_control.sock] [--timeout=300]
#
# Exit: 0 = M18_SW1_TOUCH_ACCEPTANCE result=PASS; non-zero otherwise.
#
# Sourcing guard: `RUN_M18_SW1_TOUCH_ACCEPTANCE_LIB=1 . scripts/run_m18_sw1_touch_acceptance.sh`
# defines the pure helpers (parse_rec_scale_file, resolve_rec_scale,
# stop_stale_services, confirm_services_stopped, verify_*, match_result,
# classify_result) and returns without executing main -- used by
# scripts/test_m18_sw1_touch_acceptance.sh.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/common.sh"
. "$SCRIPT_DIR/process_guard.sh"

# ---- defaults ----------------------------------------------------------------
UI_SOCK="/run/sdr_amr_ui.sock"
CTL_SOCK="/run/sdr_amr_control.sock"
UI_PID_FILE="/tmp/sdr_ui_live/ui_live.pid"
UI_LOG="/tmp/sdr_ui_live/ui_live.log"
TIMEOUT=300
PRODUCER_FRAMES=50000     # finite safe value (never 1e9); overridable.
REC_SCALE_OVERRIDE=""
LOG_DIR="/tmp/m18_sw1_touch_acceptance"

# Resolved binary paths.  Resolved inside main() via require_bin (fail-closed when
# not built); left empty here so sourced-library mode (host tests) needs no binary.
UI_BIN=""
PROD_BIN=""

# This run's PIDs (empty until started); _cleanup only ever touches these.
UI_PID=""
PRODUCER_PID=""

# parse_rec_scale_file <path> -> prints the numeric value on stdout, returns 0.
# STRICTLY rejects multi-line files -- the file must contain exactly ONE
# well-formed `rec_scale=<value>` line (and no other non-blank line).  Missing,
# malformed, non-positive, zero, NaN/inf, or multi-line all fail closed.
parse_rec_scale_file() {
    local f="$1" val count nonblank
    if [ ! -f "$f" ]; then
        echo "parse_rec_scale_file: not found: $f" >&2
        return 1
    fi
    count="$(grep -cE '^rec_scale=[[:space:]]*[0-9]+([.][0-9]+)?([eE][+-]?[0-9]+)?[[:space:]]*$' "$f" || true)"
    if [ "$count" -ne 1 ]; then
        echo "parse_rec_scale_file: expected exactly one 'rec_scale=<value>' line, found $count: $f" >&2
        return 1
    fi
    nonblank="$(grep -cvE '^[[:space:]]*$' "$f" || true)"
    if [ "$nonblank" -ne 1 ]; then
        echo "parse_rec_scale_file: multi-line rec_scale rejected ($nonblank non-blank lines): $f" >&2
        return 1
    fi
    val="$(grep -E '^rec_scale=[[:space:]]*[0-9]+([.][0-9]+)?([eE][+-]?[0-9]+)?[[:space:]]*$' "$f" \
             | sed -E 's/^rec_scale=[[:space:]]*//; s/[[:space:]]*$//')"
    # Strictly positive finite number (rejects 0 / negative / NaN / inf).
    awk -v v="$val" 'BEGIN{ exit (v ~ /^[0-9]+([.][0-9]+)?([eE][+-]?[0-9]+)?$/ && (v+0) > 0) ? 0 : 1 }' \
        || { echo "parse_rec_scale_file: invalid value '$val' in $f" >&2; return 1; }
    printf '%s\n' "$val"
    return 0
}

# resolve_rec_scale -> prints the rec_scale to use on stdout, returns 0.
resolve_rec_scale() {
    if [ -n "$REC_SCALE_OVERRIDE" ]; then
        awk -v v="$REC_SCALE_OVERRIDE" 'BEGIN{ exit (v ~ /^[0-9]+([.][0-9]+)?([eE][+-]?[0-9]+)?$/ && (v+0) > 0) ? 0 : 1 }' \
            || { echo "M18_SW1_TOUCH_ACCEPTANCE_PREP_FAIL: --rec-scale value invalid: '$REC_SCALE_OVERRIDE'" >&2; return 2; }
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
    echo "M18_SW1_TOUCH_ACCEPTANCE_PREP_FAIL: rec_scale.txt not found (current dir or package root)." >&2
    echo "  Calibrate first:  ./scripts/run_calibrate_rec_scale.sh" >&2
    echo "  (writes rec_scale.txt into the package root), or pass --rec-scale=<value>." >&2
    return 2
}

# stop_stale_services -> best-effort stop every stale UI / Gate 9 producer.
stop_stale_services() {
    local name p
    echo "M18_SW1_TOUCH_ACCEPTANCE_STEP stop_stale_services"
    for name in board_ui_live_12class board_gate9_full_chain_12class; do
        for p in $(find_pids_named "$name"); do
            if [ "$p" != "$$" ]; then
                echo "  stopping stale $name pid=$p"
                stop_pid "$p"
            fi
        done
    done
    if [ -f "$UI_PID_FILE" ]; then
        local oldp="$(cat "$UI_PID_FILE" 2>/dev/null || true)"
        if [ -n "$oldp" ] && [ "$oldp" != "$$" ] && pid_matches_bin "$oldp" "$UI_BIN"; then
            echo "  stopping stale pidfile pid=$oldp"
            stop_pid "$oldp"
        fi
        rm -f "$UI_PID_FILE"
    fi
    echo "M18_SW1_TOUCH_ACCEPTANCE_STEP stop_stale_services done"
}

# confirm_services_stopped -> 0 iff NO stale UI / Gate 9 process remains.
confirm_services_stopped() {
    local name p leftover=0
    for name in board_ui_live_12class board_gate9_full_chain_12class; do
        for p in $(find_pids_named "$name"); do
            if [ "$p" != "$$" ]; then
                echo "M18_SW1_TOUCH_ACCEPTANCE_PREP_FAIL: stale $name still running pid=$p" >&2
                leftover=1
            fi
        done
    done
    if [ "$leftover" -ne 0 ]; then
        echo "  stop_stale_services() failed to clear all old UI/Gate9 processes." >&2
        return 1
    fi
    echo "M18_SW1_TOUCH_ACCEPTANCE_STEP confirm_services_stopped ok"
    return 0
}

# wait_for_socket <sock> <label> -> returns 0 when the socket is SERVED (node exists
# AND a live process has it bound), i.e. never satisfied by a stale node.
wait_for_socket() {
    local sock="$1" label="$2" deadline
    deadline=$(( $(date +%s) + TIMEOUT ))
    while [ "$(date +%s)" -lt "$deadline" ]; do
        socket_served "$sock" && return 0
        sleep 1
    done
    echo "M18_SW1_TOUCH_ACCEPTANCE_PREP_FAIL: $label socket not served within ${TIMEOUT}s: $sock" >&2
    return 1
}

# verify_ui / verify_producer -> PID identity (right executable) + socket ownership.
verify_ui() {
    if ! pid_matches_bin "$UI_PID" "$UI_BIN"; then
        echo "M18_SW1_TOUCH_ACCEPTANCE_PREP_FAIL: UI PID $UI_PID is not the expected binary $UI_BIN" >&2
        return 1
    fi
    if ! socket_served_by "$UI_SOCK" "$UI_PID"; then
        echo "M18_SW1_TOUCH_ACCEPTANCE_PREP_FAIL: UI socket $UI_SOCK not owned by UI PID $UI_PID" >&2
        return 1
    fi
    echo "M18_SW1_TOUCH_ACCEPTANCE_STEP verify_ui pid=$UI_PID exe=$UI_BIN sock=$UI_SOCK ok"
    return 0
}

verify_producer() {
    if ! pid_matches_bin "$PRODUCER_PID" "$PROD_BIN"; then
        echo "M18_SW1_TOUCH_ACCEPTANCE_PREP_FAIL: producer PID $PRODUCER_PID is not the expected binary $PROD_BIN" >&2
        return 1
    fi
    if ! socket_served_by "$CTL_SOCK" "$PRODUCER_PID"; then
        echo "M18_SW1_TOUCH_ACCEPTANCE_PREP_FAIL: control socket $CTL_SOCK not owned by producer PID $PRODUCER_PID" >&2
        return 1
    fi
    echo "M18_SW1_TOUCH_ACCEPTANCE_STEP verify_producer pid=$PRODUCER_PID exe=$PROD_BIN sock=$CTL_SOCK ok"
    return 0
}

# _cleanup: stop ONLY this run's PIDs (never a stale/reused PID, never the shell).
# Before signalling, re-verify the PID is still alive AND still the SAME executable
# this run started: a PID that already exited, or was REUSED by a different
# process, must never be killed.
_cleanup() {
    if [ -n "${PRODUCER_PID:-}" ]; then
        stop_pid_if_matches "$PRODUCER_PID" "$PROD_BIN" || true
    fi
    if [ -n "${UI_PID:-}" ]; then
        stop_pid_if_matches "$UI_PID" "$UI_BIN" || true
    fi
}

# match_result <file> <offset> <run_id> -> prints the newest TOUCH_CONTROL_RESULT
# line appended AFTER <offset> tagged run_id=<run_id> (empty if none).  Both the
# byte-offset AND the run_id gate together prove the result belongs to THIS round,
# so a stale PASS from a previous run can never be accepted.
match_result() {
    local f="$1" off="$2" rid="$3"
    tail_since "$f" "$off" | grep 'TOUCH_CONTROL_RESULT' | grep -F "run_id=$rid" | tail -n 1
}

# classify_result <result-line> -> prints PASS or FAIL on stdout (returns 0 iff PASS).
classify_result() {
    case "$1" in
        *"result=PASS"*) printf 'PASS\n'; return 0 ;;
        *) printf 'FAIL\n'; return 1 ;;
    esac
}

# await_finalize_test -> 0 when the human types FINALIZE_TEST on stdin; non-zero on
# timeout, UI-early-exit, or Gate9-early-exit (all fail-closed).  While waiting it
# re-checks that BOTH this run's UI and producer are still alive (and the control
# socket still served), so a silently-dead producer can never leave the acceptance
# hanging into a false verdict.
await_finalize_test() {
    local line deadline
    deadline=$(( $(date +%s) + TIMEOUT ))
    echo "M18_SW1_TOUCH_ACCEPTANCE_STEP awaiting_finalize timeout=${TIMEOUT}s run_id=$RUN_ID"
    echo "   Perform the touch sequence on the MODE page now.  When every tap has"
    echo "   landed (APPLIED), type FINALIZE_TEST and press Enter.  Ctrl-C aborts."
    while [ "$(date +%s)" -lt "$deadline" ]; do
        if ! pid_alive "$UI_PID"; then
            echo "M18_SW1_TOUCH_ACCEPTANCE_PREP_FAIL: UI exited early pid=$UI_PID" >&2
            return 1
        fi
        if ! pid_alive "$PRODUCER_PID" || ! socket_served "$CTL_SOCK"; then
            echo "M18_SW1_TOUCH_ACCEPTANCE_PREP_FAIL: Gate9 producer exited early pid=$PRODUCER_PID (control socket $CTL_SOCK no longer served)" >&2
            return 1
        fi
        if read -r -t 1 line && [ "$line" = "FINALIZE_TEST" ]; then
            echo "M18_SW1_TOUCH_ACCEPTANCE_STEP finalizing run_id=$RUN_ID"
            return 0
        fi
        # Bound the EOF spin: `read -t` returns immediately on a closed stdin, so a
        # non-tty invocation would otherwise busy-loop.  On a tty this adds negligible
        # latency on top of the 1s read timeout.  A second FINALIZE_TEST can never
        # double-fire: we return on the first and the next line is never read.
        sleep 0.1
    done
    echo "M18_SW1_TOUCH_ACCEPTANCE_PREP_FAIL: no FINALIZE_TEST within ${TIMEOUT}s" >&2
    return 1
}

# finalize_and_verdict -> stop UI then producer, wait for the UI's exit, read the
# SINGLE result for THIS run_id, and print EXACTLY ONE verdict line.  Returns 0 iff
# PASS.
finalize_and_verdict() {
    # (8)(10) stop THIS run's UI first: its clean SIGTERM exit emits the single
    # TOUCH_CONTROL_RESULT (the loop checks g_stop_requested and runs the normal
    # exit block).  The producer is stopped right after; stopping it first would
    # drop the control channel before the UI computes its verdict.
    stop_pid_if_matches "$UI_PID" "$UI_BIN" || true
    stop_pid_if_matches "$PRODUCER_PID" "$PROD_BIN" || true

    # Wait for the UI to actually exit so its result line is fully flushed to the log.
    local i=0
    while pid_alive "$UI_PID" && [ "$i" -lt 50 ]; do
        sleep 0.1
        i=$((i + 1))
    done

    # (9) read the SINGLE result for THIS run_id appended after LOG_OFFSET.
    local result verdict
    result="$(match_result "$UI_LOG" "$LOG_OFFSET" "$RUN_ID")"
    if [ -z "$result" ]; then
        verdict="FAIL"
        echo "M18_SW1_TOUCH_ACCEPTANCE_PREP_FAIL: no TOUCH_CONTROL_RESULT for run_id=$RUN_ID in $UI_LOG" >&2
    else
        verdict="$(classify_result "$result")"
    fi

    # (11) print EXACTLY ONE verdict line; there is no second verdict afterwards.
    echo "M18_SW1_TOUCH_ACCEPTANCE result=$verdict run_id=$RUN_ID"
    if [ "$verdict" = "PASS" ]; then return 0; else return 1; fi
}

main() {
    mkdir -p "$LOG_DIR"

    # Resolve binary paths now (fail-closed if not built).
    UI_BIN="$(require_bin board_ui_live_12class)"
    PROD_BIN="$(require_bin board_gate9_full_chain_12class)"

    # trap EXIT/INT/TERM -> kill only this run's PIDs.  INT/TERM re-raise the exit
    # code; the EXIT trap performs the actual cleanup.
    trap _cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM

    # Resolve rec_scale FIRST (fail-closed before touching any process).
    REC_SCALE="$(resolve_rec_scale)" || exit 2

    banner "M18-SW1 touch acceptance (stop stale -> UI -> digital producer -> touch -> FINALIZE_TEST)"

    # (1) stop + confirm no stale UI/Gate9, then start a FRESH UI.
    stop_stale_services
    confirm_services_stopped || exit 2

    # (4) unique run id minted once per run.
    RUN_ID="$(run_id_new)"
    echo "M18_SW1_TOUCH_ACCEPTANCE_STEP run_id=$RUN_ID"

    # (2) start THIS round's UI (fresh), forward --run-id so the UI embeds it in its
    # result line, then block for its data socket and verify PID + ownership.
    echo "M18_SW1_TOUCH_ACCEPTANCE_STEP start_ui sock=$UI_SOCK run_id=$RUN_ID"
    "$ROOT/scripts/run_ui_live.sh" --sock="$UI_SOCK" --ctl-sock="$CTL_SOCK" --run-id="$RUN_ID" \
        >"$LOG_DIR/ui_live.log" 2>&1 \
        || { echo "M18_SW1_TOUCH_ACCEPTANCE_PREP_FAIL: UI server failed to start" >&2; exit 2; }

    # The UI PID file is REQUIRED: missing, empty, non-numeric, or wrong-identity
    # must fail-closed (never silently skip verification).
    if [ ! -f "$UI_PID_FILE" ]; then
        echo "M18_SW1_TOUCH_ACCEPTANCE_PREP_FAIL: UI PID file missing: $UI_PID_FILE" >&2
        exit 2
    fi
    UI_PID="$(cat "$UI_PID_FILE" 2>/dev/null || true)"
    case "$UI_PID" in
        ''|*[!0-9]*)
            echo "M18_SW1_TOUCH_ACCEPTANCE_PREP_FAIL: UI PID file empty or non-numeric: '$UI_PID'" >&2
            exit 2
            ;;
    esac
    wait_for_socket "$UI_SOCK" "UI (data)" || exit 2
    verify_ui || exit 2

    # (4) record this run's log offset ONLY AFTER the fresh UI has started AND its
    # PID identity + socket ownership are all verified.  run_ui_live.sh TRUNCATES
    # the UI log at startup, so an offset captured BEFORE startup could point past
    # EOF of the new (smaller) log and silently miss this run's result.
    LOG_OFFSET="$(log_offset_of "$UI_LOG")"
    echo "M18_SW1_TOUCH_ACCEPTANCE_STEP log_offset=$LOG_OFFSET"

    # (3) start THIS round's long-running digital producer (never offline), after
    # UI.  Pass the SAME custom control socket so UI + producer agree.
    echo "M18_SW1_TOUCH_ACCEPTANCE_STEP start_producer phase=digital frames=$PRODUCER_FRAMES rec_scale=$REC_SCALE ctl_sock=$CTL_SOCK"
    "$ROOT/scripts/run_gate9_ui.sh" \
        --phase=digital \
        --frames="$PRODUCER_FRAMES" \
        --rec-scale="$REC_SCALE" \
        --ctl-sock="$CTL_SOCK" \
        --sock="$UI_SOCK" \
        >"$LOG_DIR/gate9_digital.log" 2>&1 &
    PRODUCER_PID=$!

    # Block for the producer's control socket, SERVED (fail-closed).
    if ! wait_for_socket "$CTL_SOCK" "Gate 9 control"; then
        echo "  producer log tail:" >&2
        tail -n 20 "$LOG_DIR/gate9_digital.log" >&2 || true
        exit 2
    fi
    verify_producer || exit 2

    # (5)(6)(7) human performs the touch sequence, then types FINALIZE_TEST.
    await_finalize_test || exit 2

    # (8)(9)(10)(11) stop -> wait for exit -> read single result -> ONE verdict.
    finalize_and_verdict
}

if [ "${RUN_M18_SW1_TOUCH_ACCEPTANCE_LIB:-0}" = "1" ]; then
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
        *) echo "run_m18_sw1_touch_acceptance.sh: unknown option: $a" >&2; exit 2 ;;
    esac
done

main
