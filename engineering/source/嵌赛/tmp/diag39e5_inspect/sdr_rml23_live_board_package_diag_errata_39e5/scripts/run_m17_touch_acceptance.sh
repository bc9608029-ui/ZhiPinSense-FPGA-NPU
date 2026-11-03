#!/usr/bin/env bash
# run_m17_touch_acceptance.sh -- M17.3 corrected board touch acceptance orchestration.
#
# One-shot, ordered orchestration for the third-page (MODE) physical-touch
# acceptance.  It fixes the two M17 acceptance-flow errata (M17.1), hardens the
# process/log/socket handling so the acceptance is fail-closed and honest (M17.2),
# and closes the remaining log-offset / PID-reuse / PID-file gaps (M17.3):
#
#   * the touch producer MUST be a LONG-RUNNING digital producer, NOT
#     `run_gate9_ui.sh --phase=offline` (offline replays finite golden samples
#     and exits -- it is never a long-running producer);                       [M17.1]
#   * the start order MUST be UI-first: UI -> wait UI socket -> long-running
#     digital producer -> wait control socket -> touch acceptance;             [M17.1]
#   * the default producer `--frames` is now a FINITE safe value (not 1e9);    [M17.2 #1]
#   * every acceptance FIRST stops + confirms no stale UI/Gate9 process, then
#     starts a fresh UI from THIS package;                                     [M17.2 #2]
#   * PID / executable-path / socket-ownership are verified after start;       [M17.2 #3]
#   * a unique run_id is minted and the touch test only accepts a
#     TOUCH_CONTROL_RESULT appended AFTER this run's recorded log offset;      [M17.2 #4]
#   * the custom control socket is passed to BOTH the UI and the producer;     [M17.2 #5]
#   * the control socket is checked as SERVED (not just an existing node);     [M17.2 #6]
#   * rec_scale.txt must contain exactly ONE `rec_scale=<value>` line;         [M17.2 #7]
#   * traps on EXIT/INT/TERM kill ONLY this run's PIDs.                        [M17.2 #8]
#   * LOG_OFFSET is recorded AFTER the fresh UI has started and its PID/socket
#     ownership are verified (the UI log is truncated at startup);             [M17.3 #1]
#   * the default producer `--frames` is lowered to 50000;                     [M17.3 #2]
#   * cleanup re-verifies each PID is still the SAME executable before kill
#     (an exited or reused PID is never signalled);                            [M17.3 #3]
#   * a missing / empty / non-numeric / wrong-identity UI PID file fails
#     closed (verification is never silently skipped).                         [M17.3 #4]
#
# This script ONLY starts/stops processes and supervises.  It does NOT drive the
# touchscreen and does NOT use mode_ctl.sh to substitute manual touch: the human
# performs the taps, and the verdict comes from the UI's own TOUCH_CONTROL_RESULT
# line (via scripts/test_touch_mode_control.sh).
#
# Process-safety helpers (PID identity, socket liveness/ownership, byte-offset log
# tailing, unique run ids) live in scripts/process_guard.sh; they use only /proc +
# coreutils (no lsof/fuser/pgrep dependency on the board).
#
# Usage (as root):
#   ./scripts/run_m17_touch_acceptance.sh [--rec-scale=1.234] [--producer-frames=50000]
#       [--ui-sock=/run/sdr_amr_ui.sock] [--control-sock=/run/sdr_amr_control.sock]
#       [--timeout=300]
#
# Exit: 0 = M17_TOUCH_ACCEPTANCE result=PASS; non-zero otherwise.
#
# Sourcing guard: `RUN_M17_TOUCH_ACCEPTANCE_LIB=1 . scripts/run_m17_touch_acceptance.sh`
# defines the pure helpers (parse_rec_scale_file, resolve_rec_scale, stop_stale_services,
# confirm_services_stopped, verify_*) and returns without executing main -- used by
# scripts/test_m17_touch_acceptance.sh.
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
PRODUCER_FRAMES=50000     # M17.3: finite safe value (was 2000000); overridable.
REC_SCALE_OVERRIDE=""
LOG_DIR="/tmp/m17_touch_acceptance"

# Resolved binary paths.  Resolved inside main() via require_bin (fail-closed when
# not built); left empty here so sourced-library mode (host tests) needs no binary.
UI_BIN=""
PROD_BIN=""

# This run's PIDs (empty until started); _cleanup only ever touches these.
UI_PID=""
PRODUCER_PID=""

# parse_rec_scale_file <path> -> prints the numeric value on stdout, returns 0.
# M17.2: STRICTLY rejects multi-line files -- the file must contain exactly ONE
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

# stop_stale_services -> best-effort stop every stale UI / Gate 9 producer.
# Uses find_pids_named (by executable basename) plus the UI PID file as a
# fallback.  Never signals the orchestrator's own PID.
stop_stale_services() {
    local name p
    echo "M17_TOUCH_ACCEPTANCE_STEP stop_stale_services"
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
    echo "M17_TOUCH_ACCEPTANCE_STEP stop_stale_services done"
}

# confirm_services_stopped -> 0 iff NO stale UI / Gate 9 process remains.
confirm_services_stopped() {
    local name p leftover=0
    for name in board_ui_live_12class board_gate9_full_chain_12class; do
        for p in $(find_pids_named "$name"); do
            if [ "$p" != "$$" ]; then
                echo "M17_TOUCH_ACCEPTANCE_PREP_FAIL: stale $name still running pid=$p" >&2
                leftover=1
            fi
        done
    done
    if [ "$leftover" -ne 0 ]; then
        echo "  stop_stale_services() failed to clear all old UI/Gate9 processes." >&2
        return 1
    fi
    echo "M17_TOUCH_ACCEPTANCE_STEP confirm_services_stopped ok"
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
    echo "M17_TOUCH_ACCEPTANCE_PREP_FAIL: $label socket not served within ${TIMEOUT}s: $sock" >&2
    return 1
}

# verify_ui / verify_producer -> PID identity (right executable) + socket ownership.
verify_ui() {
    if ! pid_matches_bin "$UI_PID" "$UI_BIN"; then
        echo "M17_TOUCH_ACCEPTANCE_PREP_FAIL: UI PID $UI_PID is not the expected binary $UI_BIN" >&2
        return 1
    fi
    if ! socket_served_by "$UI_SOCK" "$UI_PID"; then
        echo "M17_TOUCH_ACCEPTANCE_PREP_FAIL: UI socket $UI_SOCK not owned by UI PID $UI_PID" >&2
        return 1
    fi
    echo "M17_TOUCH_ACCEPTANCE_STEP verify_ui pid=$UI_PID exe=$UI_BIN sock=$UI_SOCK ok"
    return 0
}

verify_producer() {
    if ! pid_matches_bin "$PRODUCER_PID" "$PROD_BIN"; then
        echo "M17_TOUCH_ACCEPTANCE_PREP_FAIL: producer PID $PRODUCER_PID is not the expected binary $PROD_BIN" >&2
        return 1
    fi
    if ! socket_served_by "$CTL_SOCK" "$PRODUCER_PID"; then
        echo "M17_TOUCH_ACCEPTANCE_PREP_FAIL: control socket $CTL_SOCK not owned by producer PID $PRODUCER_PID" >&2
        return 1
    fi
    echo "M17_TOUCH_ACCEPTANCE_STEP verify_producer pid=$PRODUCER_PID exe=$PROD_BIN sock=$CTL_SOCK ok"
    return 0
}

# _cleanup: stop ONLY this run's PIDs (never a stale/reused PID, never the shell).
# [M17.3] before signalling, re-verify the PID is still alive AND still the SAME
# executable this run started (UI_BIN / PROD_BIN): a PID that already exited, or
# was REUSED by a different process, must never be killed.
_cleanup() {
    if [ -n "${PRODUCER_PID:-}" ]; then
        stop_pid_if_matches "$PRODUCER_PID" "$PROD_BIN" || true
    fi
    if [ -n "${UI_PID:-}" ]; then
        stop_pid_if_matches "$UI_PID" "$UI_BIN" || true
    fi
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

    banner "M17.2 touch acceptance (stop stale -> UI -> digital producer -> touch)"

    # [M17.2 #2] stop + confirm no stale UI/Gate9, then start a FRESH UI.
    stop_stale_services
    confirm_services_stopped || exit 2

    # [M17.2 #4] unique run id minted once per run (the log offset is recorded
    # AFTER the fresh UI is fully up and verified -- see [M17.3] below).
    RUN_ID="$(run_id_new)"
    echo "M17_TOUCH_ACCEPTANCE_STEP run_id=$RUN_ID"

    # Start UI first (fresh), then block for its data socket (fail-closed).
    echo "M17_TOUCH_ACCEPTANCE_STEP start_ui sock=$UI_SOCK"
    "$ROOT/scripts/run_ui_live.sh" --sock="$UI_SOCK" --ctl-sock="$CTL_SOCK" \
        >"$LOG_DIR/ui_live.log" 2>&1 \
        || { echo "M17_TOUCH_ACCEPTANCE_PREP_FAIL: UI server failed to start" >&2; exit 2; }

    # [M17.3] the UI PID file is REQUIRED: missing, empty, non-numeric, or
    # wrong-identity must fail-closed (never silently skip verification).
    if [ ! -f "$UI_PID_FILE" ]; then
        echo "M17_TOUCH_ACCEPTANCE_PREP_FAIL: UI PID file missing: $UI_PID_FILE" >&2
        exit 2
    fi
    UI_PID="$(cat "$UI_PID_FILE" 2>/dev/null || true)"
    case "$UI_PID" in
        ''|*[!0-9]*)
            echo "M17_TOUCH_ACCEPTANCE_PREP_FAIL: UI PID file empty or non-numeric: '$UI_PID'" >&2
            exit 2
            ;;
    esac
    wait_for_socket "$UI_SOCK" "UI (data)" || exit 2
    verify_ui || exit 2

    # [M17.3] record this run's log offset ONLY AFTER the fresh UI has started AND
    # its PID identity + socket ownership are all verified.  run_ui_live.sh
    # TRUNCATES the UI log at startup, so an offset captured BEFORE startup can
    # point past EOF of the new (smaller) log and silently miss this run's
    # TOUCH_CONTROL_RESULT.
    LOG_OFFSET="$(log_offset_of "$UI_LOG")"
    echo "M17_TOUCH_ACCEPTANCE_STEP log_offset=$LOG_OFFSET"

    # Start the LONG-RUNNING digital producer (never offline), after UI.  Pass the
    # SAME custom control socket to the producer so UI + producer agree [M17.2 #5].
    echo "M17_TOUCH_ACCEPTANCE_STEP start_producer phase=digital frames=$PRODUCER_FRAMES rec_scale=$REC_SCALE ctl_sock=$CTL_SOCK"
    "$ROOT/scripts/run_gate9_ui.sh" \
        --phase=digital \
        --frames="$PRODUCER_FRAMES" \
        --rec-scale="$REC_SCALE" \
        --ctl-sock="$CTL_SOCK" \
        --sock="$UI_SOCK" \
        >"$LOG_DIR/gate9_digital.log" 2>&1 &
    PRODUCER_PID=$!

    # Block for the producer's control socket, SERVED (fail-closed) [M17.2 #6].
    if ! wait_for_socket "$CTL_SOCK" "Gate 9 control"; then
        echo "  producer log tail:" >&2
        tail -n 20 "$LOG_DIR/gate9_digital.log" >&2 || true
        exit 2
    fi
    verify_producer || exit 2

    # [M17.2 #4] the touch test only accepts a TOUCH_CONTROL_RESULT appended after
    # this run's log offset, tagged with this run_id.
    echo "M17_TOUCH_ACCEPTANCE_STEP run_touch_acceptance timeout=${TIMEOUT}s run_id=$RUN_ID log_offset=$LOG_OFFSET"
    set +e
    "$ROOT/scripts/test_touch_mode_control.sh" \
        --control-sock="$CTL_SOCK" \
        --ui-log="$UI_LOG" \
        --log-offset="$LOG_OFFSET" \
        --run-id="$RUN_ID" \
        --timeout="$TIMEOUT"
    RC=$?
    set -e

    if [ "$RC" -eq 0 ]; then
        echo "M17_TOUCH_ACCEPTANCE result=PASS run_id=$RUN_ID"
    else
        echo "M17_TOUCH_ACCEPTANCE result=FAIL run_id=$RUN_ID (test_touch_mode_control exit=$RC)"
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
