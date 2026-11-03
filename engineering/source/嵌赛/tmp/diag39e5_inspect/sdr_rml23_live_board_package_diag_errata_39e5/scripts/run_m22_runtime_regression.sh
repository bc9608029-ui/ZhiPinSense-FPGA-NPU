#!/usr/bin/env bash
# run_m22_runtime_regression.sh -- M22 §六 fast regression (Gate 9 --phase=offline,
# --count=240), proving the M22 fixes hold WITHOUT waiting for a 10000-frame run.
#
# The offline phase replays the deployment_golden inputs through the real NPU and
# gates `match_rate >= --min-match-rate` (default 0.90) -- i.e. the NPU output is
# byte-for-byte IDENTICAL to the frozen golden argmax, which is the §六 "NPU results
# identical" criterion -- while the M22 lifecycle discipline (reopen==0, apply==1,
# rearm reset_count==frames-1) is checked by the binary's own finish_m22_runtime()
# and reported in the single `M22_RUNTIME_RESULT result=PASS|FAIL ...` line.
#
# This script runs that binary against a FRESH log + perf file in a unique per-run
# directory, waits for it, reads back the single M22_RUNTIME_RESULT verdict, and
# prints EXACTLY ONE final line:
#
#   M22_RUNTIME_REGRESSION result=PASS|FAIL|PREP_FAIL run_id=... count=... perf_file=...
#
# Fail-closed (non-zero) on: binary missing, device-not-found, no M22_RUNTIME_RESULT
# line, empty/missing perf JSON, or phase failure.  Cleanup only signals THIS run's
# PID after re-verifying liveness + executable identity.
#
# Usage (as root):
#   ./scripts/run_m22_runtime_regression.sh
#   ./scripts/run_m22_runtime_regression.sh --count=1000 --min-match-rate=0.95
#
# Exit: 0 = M22_RUNTIME_REGRESSION result=PASS; 1 = FAIL; 2 = PREP_FAIL.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/common.sh"
. "$SCRIPT_DIR/process_guard.sh"
. "$SCRIPT_DIR/m22_harness.sh"

# ---- defaults ----------------------------------------------------------------
PHASE="offline"
COUNT=240
MIN_MATCH_RATE="0.90"
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
    RUN_DIR="$RUNS_ROOT/m22_runtime_regression/$RUN_ID"
    mkdir -p "$RUN_DIR"
    LOG="$RUN_DIR/gate9_offline.log"
    PERF="$RUN_DIR/m22_runtime_regression.json"

    banner "M22 §六 runtime regression (phase=$PHASE count=$COUNT run_id=$RUN_ID)"
    echo "M22_RUNTIME_REGRESSION_STEP start run_id=$RUN_ID count=$COUNT phase=$PHASE"

    # Start THIS run's binary against a FRESH log + perf file.  The PID is returned
    # via a caller-named variable (NOT command substitution), so the background job
    # is a DIRECT child of THIS shell and `wait` below owns it (M22.1 harness errata).
    run_gate9_captured PROD_PID "$LOG" "$BIN" \
        --model-json="$MODEL_JSON" \
        --model-raw="$MODEL_RAW" \
        --model-sha="$MODEL_RAW_SHA" \
        --golden="$GOLDEN" \
        --phase="$PHASE" \
        --count="$COUNT" \
        --min-match-rate="$MIN_MATCH_RATE" \
        --perf-file="$PERF"
    echo "M22_RUNTIME_REGRESSION_STEP running pid=$PROD_PID"

    local rc=0
    wait "$PROD_PID" || rc=$?
    PROD_PID=""

    local result_line perf_ok verdict
    result_line="$(m22_result_line "$LOG")"
    perf_ok="$(m22_perf_nonempty "$PERF")"
    verdict="$(m22_run_verdict "$rc" "$result_line" "$perf_ok")"

    if [ -n "$result_line" ]; then
        echo "M22_RUNTIME_REGRESSION_STEP runtime_result: $result_line"
    else
        echo "M22_RUNTIME_REGRESSION_PREP_FAIL: no M22_RUNTIME_RESULT line in $LOG" >&2
        tail -n 20 "$LOG" >&2 || true
    fi

    echo "M22_RUNTIME_REGRESSION result=$verdict run_id=$RUN_ID count=$COUNT phase=$PHASE perf_file=$PERF"
    case "$verdict" in
        PASS) return 0 ;;
        PREP_FAIL) return 2 ;;
        *) return 1 ;;
    esac
}

if [ "${RUN_M22_RUNTIME_REGRESSION_LIB:-0}" = "1" ]; then
    return 0 2>/dev/null || exit 0
fi

for a in "$@"; do
    case "$a" in
        --phase=*) PHASE="${a#--phase=}" ;;
        --count=*) COUNT="${a#--count=}" ;;
        --min-match-rate=*) MIN_MATCH_RATE="${a#--min-match-rate=}" ;;
        --runs-root=*) RUNS_ROOT="${a#--runs-root=}" ;;
        *) echo "run_m22_runtime_regression.sh: unknown option: $a" >&2; exit 2 ;;
    esac
done

main
