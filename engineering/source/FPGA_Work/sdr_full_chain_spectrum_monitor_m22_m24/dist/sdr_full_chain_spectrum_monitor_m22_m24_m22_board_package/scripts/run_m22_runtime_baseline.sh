#!/usr/bin/env bash
# run_m22_runtime_baseline.sh -- M22 §三 runtime baseline (Gate 9 --phase=ambient,
# >=10000 frames), the board-side measurement that feeds docs/M22_RUNTIME_BASELINE.md.
#
# Runs the Gate 9 binary in the RX-only ambient phase for --frames frames (default
# 10000, per §三.11 ">=10000 帧"), which drives the FULL SDR -> DSP -> presence ->
# NPU -> UI chain with a real receiver.  The binary's own M22 instrumentation
# (finish_m22_runtime) records the nine per-stage latencies (DeviceOpen / ModelLoad /
# RfConfig / RxRefill / Preprocess / NpuInfer / Postprocess / UiSubmit / FrameTotal)
# plus RSS/FD/thread/cpu resource samples, and at the end emits EXACTLY ONE
# `M22_RUNTIME_RESULT result=PASS|FAIL ...` line and a `--perf-file` JSON.
#
# This script's ONLY job is to run that binary against a FRESH log + perf file in a
# unique per-run directory, wait for it, read back the single M22_RUNTIME_RESULT
# verdict, and print EXACTLY ONE final line:
#
#   M22_RUNTIME_BASELINE result=PASS|FAIL|PREP_FAIL run_id=... frames=... perf_file=...
#
# Fail-closed (non-zero) on: binary missing, device-not-found, no M22_RUNTIME_RESULT
# line, empty/missing perf JSON, or phase failure.  Cleanup only signals THIS run's
# PID after re-verifying liveness + executable identity (never a stale/reused PID).
#
# Usage (as root, RX antenna on the external input; no TX, tx_active=0):
#   ./scripts/run_m22_runtime_baseline.sh
#   ./scripts/run_m22_runtime_baseline.sh --frames=20000 --summary-interval=1000
#   ./scripts/run_m22_runtime_baseline.sh --rec-scale=4.096
#
# Exit: 0 = M22_RUNTIME_BASELINE result=PASS; 1 = FAIL; 2 = PREP_FAIL.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/common.sh"
. "$SCRIPT_DIR/process_guard.sh"
. "$SCRIPT_DIR/m22_harness.sh"

# ---- defaults ----------------------------------------------------------------
PHASE="ambient"
FRAMES=10000
SUMMARY_INTERVAL=1000
RX_GAIN=10
REC_SCALE="1.0"
RUNS_ROOT=""            # default: $ROOT/runs

# This run's PID (empty until started); _cleanup only ever touches it.
PROD_PID=""

# _cleanup: stop ONLY this run's binary, re-verifying liveness + executable identity.
_cleanup() {
    if [ -n "${PROD_PID:-}" ]; then
        stop_pid_if_matches "$PROD_PID" "$BIN" || true
    fi
}

main() {
    BIN="$(require_bin board_gate9_full_chain_12class)"
    require_libiio_runtime

    trap _cleanup EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM

    RUNS_ROOT="${RUNS_ROOT:-$ROOT/runs}"
    RUN_ID="$(m22_run_id)"
    RUN_DIR="$RUNS_ROOT/m22_runtime_baseline/$RUN_ID"
    mkdir -p "$RUN_DIR"
    LOG="$RUN_DIR/gate9_ambient.log"
    PERF="$RUN_DIR/m22_runtime_baseline.json"

    banner "M22 §三 runtime baseline (phase=$PHASE frames=$FRAMES run_id=$RUN_ID)"
    echo "M22_RUNTIME_BASELINE_STEP start run_id=$RUN_ID frames=$FRAMES phase=$PHASE"

    # Start THIS run's binary against a FRESH log + perf file (both created/truncated
    # by the redirections and --perf-file below, so an old run can never leak in).
    PROD_PID="$(run_gate9_captured "$LOG" "$BIN" \
        --model-json="$MODEL_JSON" \
        --model-raw="$MODEL_RAW" \
        --model-sha="$MODEL_RAW_SHA" \
        --golden="$GOLDEN" \
        --phase="$PHASE" \
        --frames="$FRAMES" \
        --rx-gain="$RX_GAIN" \
        --rec-scale="$REC_SCALE" \
        --summary-interval="$SUMMARY_INTERVAL" \
        --perf-file="$PERF")"
    echo "M22_RUNTIME_BASELINE_STEP running pid=$PROD_PID"

    # Wait for the binary to exit on its own.  Capture the exit code WITHOUT letting
    # set -e fire on the non-zero phase-exit (a FAIL verdict is still a verdict).
    local rc=0
    wait "$PROD_PID" || rc=$?
    PROD_PID=""   # already reaped; _cleanup must not signal it again.

    # Read the SINGLE M22_RUNTIME_RESULT verdict from THIS run's log.
    local result_line perf_ok verdict
    result_line="$(m22_result_line "$LOG")"
    perf_ok="$(m22_perf_nonempty "$PERF")"
    verdict="$(m22_run_verdict "$rc" "$result_line" "$perf_ok")"

    if [ -n "$result_line" ]; then
        echo "M22_RUNTIME_BASELINE_STEP runtime_result: $result_line"
    else
        echo "M22_RUNTIME_BASELINE_PREP_FAIL: no M22_RUNTIME_RESULT line in $LOG" >&2
        tail -n 20 "$LOG" >&2 || true
    fi

    # EXACTLY ONE final verdict line.
    echo "M22_RUNTIME_BASELINE result=$verdict run_id=$RUN_ID frames=$FRAMES phase=$PHASE perf_file=$PERF"
    case "$verdict" in
        PASS) return 0 ;;
        PREP_FAIL) return 2 ;;
        *) return 1 ;;
    esac
}

if [ "${RUN_M22_RUNTIME_BASELINE_LIB:-0}" = "1" ]; then
    # Sourced as a library: define helpers only, do not execute main.
    return 0 2>/dev/null || exit 0
fi

# ---- arg parsing (after the library guard so sourced mode is cheap) ----------
for a in "$@"; do
    case "$a" in
        --phase=*) PHASE="${a#--phase=}" ;;
        --frames=*) FRAMES="${a#--frames=}" ;;
        --summary-interval=*) SUMMARY_INTERVAL="${a#--summary-interval=}" ;;
        --rx-gain=*) RX_GAIN="${a#--rx-gain=}" ;;
        --rec-scale=*) REC_SCALE="${a#--rec-scale=}" ;;
        --runs-root=*) RUNS_ROOT="${a#--runs-root=}" ;;
        *) echo "run_m22_runtime_baseline.sh: unknown option: $a" >&2; exit 2 ;;
    esac
done

main
