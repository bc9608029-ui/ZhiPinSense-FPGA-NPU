#!/usr/bin/env bash
# test_live_10000_frames.sh -- RML23 (M29 F5) stability soak: Gate 9 RML23
# --phase=digital, --frames=10000 (default), the long-run Pluto digital-loopback
# liveness test that proves the 24-class NPU -> AM-SSB merge -> 23-class UI chain
# is stable over >=10000 frames with the Open-once NPU discipline intact.
#
# Identical harness to test_live_1000_frames.sh (see its header for the full
# contract); this script only changes the default frame count to 10000 and prints
# `RML23_TEST_LIVE_LONG` as its final tag.
#
# Exit: 0 = RML23_TEST_LIVE_LONG result=PASS; 1 = FAIL; 2 = PREP_FAIL.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/common_rml23.sh"
. "$SCRIPT_DIR/process_guard.sh"
. "$SCRIPT_DIR/m22_harness.sh"

# ---- defaults ----------------------------------------------------------------
PHASE="digital"
FRAMES=10000
SUMMARY_INTERVAL=1000
RX_GAIN=10
REC_SCALE="1.0"
RUNS_ROOT=""
NCO_OFFSET=0             # pass-through to the binary's --nco-offset
RF_DIAG=""               # empty = off; "1" enables --rf-diag
RF_DIAG_INTERVAL=100     # frames between RF_DIAG summaries when enabled

PROD_PID=""

_cleanup() {
    if [ -n "${PROD_PID:-}" ]; then
        stop_pid_if_matches "$PROD_PID" "$BIN" || true
    fi
}

main() {
    BIN="$(require_bin board_gate9_full_chain_rml23)"
    require_libiio_runtime

    trap _cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM

    RUNS_ROOT="${RUNS_ROOT:-$ROOT/runs}"
    RUN_ID="$(m22_run_id)"
    RUN_DIR="$RUNS_ROOT/rml23_test_live_long/$RUN_ID"
    mkdir -p "$RUN_DIR"
    LOG="$RUN_DIR/gate9_rml23_digital.log"
    PERF="$RUN_DIR/rml23_test_live_long.json"

    # RF/CLI pass-through (always nco-offset + diag-interval; --rf-diag only on).
    RF_ARGS=(--nco-offset="$NCO_OFFSET" --rf-diag-interval="$RF_DIAG_INTERVAL")
    [ -n "$RF_DIAG" ] && RF_ARGS+=(--rf-diag)

    banner "RML23 test_live_long (phase=$PHASE frames=$FRAMES run_id=$RUN_ID)"
    echo "RML23_TEST_LIVE_LONG_STEP start run_id=$RUN_ID frames=$FRAMES phase=$PHASE"

    # Start THIS run's binary against a FRESH log + perf file.  The PID is returned
    # via a caller-named variable (NOT command substitution), so the background job
    # is a DIRECT child of THIS shell and `wait` below owns it (M22.1 harness errata).
    run_gate9_captured PROD_PID "$LOG" "$BIN" \
        --model-json="$MODEL_JSON" \
        --model-raw="$MODEL_RAW" \
        --model-sha="$MODEL_RAW_SHA" \
        --sock="$UI_SOCK" \
        --ctl-sock="$CTL_SOCK" \
        --golden="$GOLDEN" \
        --phase="$PHASE" \
        --frames="$FRAMES" \
        --rx-gain="$RX_GAIN" \
        --rec-scale="$REC_SCALE" \
        --summary-interval="$SUMMARY_INTERVAL" \
        --perf-file="$PERF" \
        "${RF_ARGS[@]}"
    echo "RML23_TEST_LIVE_LONG_STEP running pid=$PROD_PID"

    local rc=0
    wait "$PROD_PID" || rc=$?
    PROD_PID=""

    local result_line perf_ok verdict
    result_line="$(m22_result_line "$LOG")"
    perf_ok="$(m22_perf_nonempty "$PERF")"
    verdict="$(m22_run_verdict "$rc" "$result_line" "$perf_ok")"

    if [ -n "$result_line" ]; then
        echo "RML23_TEST_LIVE_LONG_STEP runtime_result: $result_line"
    else
        echo "RML23_TEST_LIVE_LONG_PREP_FAIL: no M22_RUNTIME_RESULT line in $LOG" >&2
        tail -n 20 "$LOG" >&2 || true
    fi

    echo "RML23_TEST_LIVE_LONG result=$verdict run_id=$RUN_ID frames=$FRAMES phase=$PHASE perf_file=$PERF"
    case "$verdict" in
        PASS) return 0 ;;
        PREP_FAIL) return 2 ;;
        *) return 1 ;;
    esac
}

if [ "${RML23_TEST_LIVE_LONG_LIB:-0}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi

for a in "$@"; do
    case "$a" in
        --phase=*) PHASE="${a#--phase=}" ;;
        --frames=*) FRAMES="${a#--frames=}" ;;
        --summary-interval=*) SUMMARY_INTERVAL="${a#--summary-interval=}" ;;
        --rx-gain=*) RX_GAIN="${a#--rx-gain=}" ;;
        --rec-scale=*) REC_SCALE="${a#--rec-scale=}" ;;
        --runs-root=*) RUNS_ROOT="${a#--runs-root=}" ;;
        --nco-offset=*) NCO_OFFSET="${a#--nco-offset=}" ;;
        --rf-diag) RF_DIAG=1 ;;
        --rf-diag-interval=*) RF_DIAG_INTERVAL="${a#--rf-diag-interval=}" ;;
        *) echo "test_live_10000_frames.sh: unknown option: $a" >&2; exit 2 ;;
    esac
done

main
