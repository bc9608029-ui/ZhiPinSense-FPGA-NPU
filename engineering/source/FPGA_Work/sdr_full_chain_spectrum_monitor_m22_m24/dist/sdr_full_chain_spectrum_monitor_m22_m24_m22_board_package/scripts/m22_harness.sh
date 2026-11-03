#!/usr/bin/env bash
# m22_harness.sh -- shared M22 runtime-baseline / runtime-regression helpers
# (task 39e5 M22 §三/§六/§二十).  Source-only (never executed directly).
#
# These wrap the Gate 9 binary's own M22 instrumentation (board_gate9_full_chain
# _12class.cpp finish_m22_runtime()), which prints exactly one authoritative
# `M22_RUNTIME_RESULT result=PASS|FAIL ...` line at the end of a run plus a
# `--perf-file` JSON (nine stage latencies + resource first/last/peak + the §六
# acceptance booleans).  The harness's ONLY jobs are:
#
#   * run the binary in the background against a FRESH log + perf file in a
#     unique per-run directory (so an old log can never produce a false PASS);
#   * manage ONLY this run's PID, re-verifying liveness + executable identity
#     before any signal (never a stale/reused PID);
#   * wait for the binary, then read the SINGLE M22_RUNTIME_RESULT verdict from
#     THIS run's log and print exactly ONE final result line;
#   * fail-closed (non-zero, no verdict) when the binary is missing, the device
#     is not found, or no M22_RUNTIME_RESULT line was ever produced.
#
# Sourced by scripts/run_m22_runtime_baseline.sh and
# scripts/run_m22_runtime_regression.sh.  Library guard:
#   M22_HARNESS_LIB=1 . scripts/m22_harness.sh
#
# NOTE: like process_guard.sh, this file does NOT set -e/-u; the caller manages
# its own strictness.  All helpers are set -u-safe (defaulted expansions).

# m22_run_id -> a fresh, per-invocation-unique run id (m22-tagged).
m22_run_id() {
    printf 'm22_%s_%s_%s\n' "$(date +%s)" "$$" "$RANDOM"
}

# run_gate9_captured <logfile> <bin> [args...] -> starts the Gate 9 binary in the
# background with stdout+stderr captured into <logfile>, prints its PID on stdout.
# The logfile is opened with > (truncate/create) so it holds ONLY this run's output.
run_gate9_captured() {
    local logfile="$1" bin="$2"
    shift 2
    "$bin" "$@" >"$logfile" 2>&1 &
    printf '%s\n' "$!"
}

# m22_result_line <logfile> -> prints the LAST M22_RUNTIME_RESULT line (empty if the
# binary never produced one, e.g. device-not-found before bring-up).
m22_result_line() {
    grep 'M22_RUNTIME_RESULT ' "$1" 2>/dev/null | tail -n 1 || true
}

# m22_verdict <result-line> -> prints PASS|FAIL on stdout; returns 0 iff PASS.
m22_verdict() {
    case "$1" in
        *"result=PASS"*) printf 'PASS\n'; return 0 ;;
        *) printf 'FAIL\n'; return 1 ;;
    esac
}

# m22_perf_nonempty <perf-file> -> prints 1 if the --perf-file JSON exists and is
# non-empty (contains at least one '{'), else 0.  A missing/empty/truncated perf
# file means the baseline numbers were never captured -> fail-closed.
m22_perf_nonempty() {
    if [ -f "$1" ] && [ -s "$1" ] && grep -q '{' "$1" 2>/dev/null; then
        printf '1\n'
    else
        printf '0\n'
    fi
}

# m22_run_verdict <rc> <result-line> <perf-nonempty> -> the SINGLE verdict for a
# completed run.  Prints PASS|FAIL|PREP_FAIL on stdout; returns 0 iff PASS.
#
#   rc          = the Gate 9 binary's own exit code (0 => phase PASS).
#   result-line = the last M22_RUNTIME_RESULT line (empty => the binary never
#                 reached finish_m22_runtime, e.g. device-not-found / crash
#                 before bring-up -> PREP_FAIL, no measurement).
#   perf-nonempty = 1 iff the --perf-file JSON exists and is non-empty.
#
# A clean PASS requires ALL of: the binary produced a result line, that line says
# result=PASS, the perf JSON is non-empty, AND the phase itself passed (rc == 0).
# The phase-PASS and M22-RUNTIME verdicts are independent; both must hold so a
# truncated/stream-broken run can never report a clean baseline.
m22_run_verdict() {
    local rc="$1" result_line="$2" perf_ok="$3" v
    if [ -z "$result_line" ]; then
        printf 'PREP_FAIL\n'; return 2
    fi
    if [ "$perf_ok" != "1" ]; then
        printf 'FAIL\n'; return 1
    fi
    v="$(m22_verdict "$result_line")"
    if [ "$v" = "PASS" ] && [ "$rc" = "0" ]; then
        printf 'PASS\n'; return 0
    fi
    printf 'FAIL\n'; return 1
}
