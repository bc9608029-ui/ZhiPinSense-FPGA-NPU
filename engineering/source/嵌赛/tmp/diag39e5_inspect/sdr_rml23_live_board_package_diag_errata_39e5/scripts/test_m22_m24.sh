#!/usr/bin/env bash
# test_m22_m24.sh -- host-side shell test for the M22 runtime scripts + shared
# harness (task 39e5 §二十):
#   scripts/run_m22_runtime_baseline.sh
#   scripts/run_m22_runtime_regression.sh
#   scripts/m22_harness.sh
#
# Verifies, WITHOUT touching the board or any board binary, that the M22 scripts
# are fail-closed, single-verdict, and cwd-independent:
#
#   * `bash -n` syntax of all three scripts;
#   * static checks: EXACTLY ONE verdict echo per run script; the verdict is
#     computed via m22_run_verdict (phase-PASS AND M22_RUNTIME_RESULT PASS AND
#     non-empty perf JSON); the M22_RUNTIME_RESULT line is read via m22_result_line
#     (last line, so an old-log line can never produce a false PASS); cleanup uses
#     stop_pid_if_matches (identity re-checked, never bare stop_pid); EXIT/INT/TERM
#     traps; library guards; --perf-file forwarded; baseline >=10000 frames;
#     regression default --count=240;
#   * sourced-library functional tests of the harness primitives (m22_verdict,
#     m22_run_verdict, m22_perf_nonempty, m22_result_line, m22_run_id);
#   * library-guard short-circuit: sourcing each run script as a library must NOT
#     execute main (no binary resolution, no banner).
#
# Run from anywhere inside the package (WSL/Linux); exit 0 = ALL CHECKS PASSED.
# The actual baseline/regression runs still require the board.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS="$SCRIPT_DIR/m22_harness.sh"
BASELINE="$SCRIPT_DIR/run_m22_runtime_baseline.sh"
REGRESSION="$SCRIPT_DIR/run_m22_runtime_regression.sh"
PASS=0
FAIL=0

ok()  { PASS=$((PASS+1)); echo "  ok  $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL $1"; }
section() { echo "== $1 =="; }

has() { grep -qE -- "$1" "${2:-$HARNESS}"; }

section "0. syntax: bash -n"
for f in "$HARNESS" "$BASELINE" "$REGRESSION"; do
    if bash -n "$f"; then ok "bash -n $(basename "$f")"; else bad "bash -n $(basename "$f")"; fi
done

section "1. exactly ONE verdict echo per run script"
NB="$(grep -c 'echo "M22_RUNTIME_BASELINE result=' "$BASELINE")"
NR="$(grep -c 'echo "M22_RUNTIME_REGRESSION result=' "$REGRESSION")"
if [ "$NB" -eq 1 ]; then ok "baseline: exactly one verdict echo ($NB)"; else bad "baseline: single verdict echo (got $NB)"; fi
if [ "$NR" -eq 1 ]; then ok "regression: exactly one verdict echo ($NR)"; else bad "regression: single verdict echo (got $NR)"; fi

section "2. verdict computed via m22_run_verdict (phase PASS + runtime PASS + perf)"
if has 'm22_run_verdict' "$BASELINE" && has 'm22_run_verdict' "$REGRESSION"; then
    ok "both run scripts compute the verdict via m22_run_verdict"
else
    bad "m22_run_verdict not used"
fi
if has 'm22_perf_nonempty' "$BASELINE" && has 'm22_perf_nonempty' "$REGRESSION"; then
    ok "perf JSON non-empty is a PASS precondition (m22_perf_nonempty)"
else
    bad "m22_perf_nonempty missing"
fi

section "3. M22_RUNTIME_RESULT read from a FRESH log (no old-log false PASS)"
if has 'm22_result_line' "$BASELINE" && has 'm22_result_line' "$REGRESSION"; then
    ok "both read the runtime verdict via m22_result_line (last-line, fresh log)"
else
    bad "m22_result_line not used"
fi
if has 'run_gate9_captured' "$BASELINE" && has 'run_gate9_captured' "$REGRESSION"; then
    ok "binary launched against a fresh captured log (run_gate9_captured)"
else
    bad "run_gate9_captured not used"
fi

section "4. unique run id + per-run directory (never reused)"
if has 'm22_run_id' "$BASELINE" && has 'm22_run_id' "$REGRESSION"; then
    ok "unique run id minted (m22_run_id)"
else
    bad "m22_run_id not used"
fi
if has 'mkdir -p "\$RUN_DIR"' "$BASELINE" && has 'mkdir -p "\$RUN_DIR"' "$REGRESSION"; then
    ok "fresh per-run directory created"
else
    bad "per-run directory missing"
fi

section "5. cleanup: stop_pid_if_matches only (identity re-checked), never bare stop_pid"
if has 'stop_pid_if_matches "\$PROD_PID"' "$BASELINE" && has 'stop_pid_if_matches "\$PROD_PID"' "$REGRESSION"; then
    ok "cleanup uses stop_pid_if_matches (PID liveness + executable identity)"
else
    bad "cleanup stop_pid_if_matches missing"
fi
if ! grep -qE 'stop_pid "\$PROD_PID"' "$BASELINE" && ! grep -qE 'stop_pid "\$PROD_PID"' "$REGRESSION"; then
    ok "no bare stop_pid on this run's PID"
else
    bad "bare stop_pid used in cleanup"
fi

section "6. EXIT/INT/TERM traps"
for s in "$BASELINE" "$REGRESSION"; do
    n=$(basename "$s")
    if has 'trap _cleanup EXIT' "$s"; then ok "$n: EXIT trap -> _cleanup"; else bad "$n: EXIT trap"; fi
    if has 'exit 130' "$s" && has 'exit 143' "$s"; then ok "$n: INT/TERM re-raise 130/143"; else bad "$n: INT/TERM trap"; fi
done

section "7. library guards + shared harness sourced"
if has 'RUN_M22_RUNTIME_BASELINE_LIB' "$BASELINE"; then ok "baseline library guard present"; else bad "baseline library guard"; fi
if has 'RUN_M22_RUNTIME_REGRESSION_LIB' "$REGRESSION"; then ok "regression library guard present"; else bad "regression library guard"; fi
for s in "$BASELINE" "$REGRESSION"; do
    n=$(basename "$s")
    if has 'm22_harness.sh' "$s" && has 'process_guard.sh' "$s" && has 'common.sh' "$s"; then
        ok "$n: sources common/process_guard/m22_harness"
    else
        bad "$n: missing source"
    fi
done

section "8. --perf-file forwarded (JSON captured) + phase/frame defaults"
for s in "$BASELINE" "$REGRESSION"; do
    n=$(basename "$s")
    if has '--perf-file="\$PERF"' "$s"; then ok "$n: forwards --perf-file"; else bad "$n: --perf-file"; fi
done
if has 'FRAMES=10000' "$BASELINE"; then ok "baseline default FRAMES=10000 (>=10000 per §三.11)"; else bad "baseline FRAMES=10000"; fi
if has 'COUNT=240' "$REGRESSION"; then ok "regression default COUNT=240"; else bad "regression COUNT=240"; fi
if has 'PHASE="ambient"' "$BASELINE"; then ok "baseline default phase=ambient"; else bad "baseline phase=ambient"; fi
if has 'PHASE="offline"' "$REGRESSION"; then ok "regression default phase=offline"; else bad "regression phase=offline"; fi

section "9. sourced-library: harness primitives"
# m22_harness.sh sets no set -e/-u, so it can be sourced safely under `set -u`.
. "$HARNESS"

chk() { if [ "$1" = "$2" ]; then ok "$3"; else bad "$3 (expected [$1] got [$2])"; fi; }

chk PASS "$(m22_verdict 'M22_RUNTIME_RESULT result=PASS phase=ambient')" "m22_verdict PASS"
chk FAIL "$(m22_verdict 'M22_RUNTIME_RESULT result=FAIL phase=ambient')" "m22_verdict FAIL"
chk FAIL "$(m22_verdict '')" "m22_verdict empty -> FAIL"

chk PASS "$(m22_run_verdict 0 'M22_RUNTIME_RESULT result=PASS' 1)" "run verdict PASS"
chk FAIL "$(m22_run_verdict 1 'M22_RUNTIME_RESULT result=PASS' 1)" "run verdict rc!=0 -> FAIL"
chk FAIL "$(m22_run_verdict 0 'M22_RUNTIME_RESULT result=FAIL' 1)" "run verdict runtime FAIL -> FAIL"
chk FAIL "$(m22_run_verdict 0 'M22_RUNTIME_RESULT result=PASS' 0)" "run verdict no perf -> FAIL"
chk PREP_FAIL "$(m22_run_verdict 0 '' 1)" "run verdict no result line -> PREP_FAIL"
chk PREP_FAIL "$(m22_run_verdict 2 '' 0)" "run verdict device-not-found -> PREP_FAIL"

TMP="$(mktemp -d)"
chk 0 "$(m22_perf_nonempty "$TMP/missing.json")" "m22_perf_nonempty missing -> 0"
: > "$TMP/empty.json"
chk 0 "$(m22_perf_nonempty "$TMP/empty.json")" "m22_perf_nonempty empty -> 0"
printf '%s\n' '{"result":"PASS"}' > "$TMP/ok.json"
chk 1 "$(m22_perf_nonempty "$TMP/ok.json")" "m22_perf_nonempty ok -> 1"
printf '   ' > "$TMP/ws.json"
chk 0 "$(m22_perf_nonempty "$TMP/ws.json")" "m22_perf_nonempty whitespace -> 0"

# m22_result_line returns the LAST line only (a stale earlier PASS is not seen).
printf 'M22_RUNTIME_RESULT result=PASS phase=ambient\n' > "$TMP/rl.log"
printf 'M22_RUNTIME_RESULT result=FAIL phase=ambient\n' >> "$TMP/rl.log"
if echo "$(m22_result_line "$TMP/rl.log")" | grep -q 'result=FAIL'; then
    ok "m22_result_line returns the LAST line (stale PASS not seen)"
else
    bad "m22_result_line last-line (got '$(m22_result_line "$TMP/rl.log")')"
fi
if [ -z "$(m22_result_line "$TMP/no_such.log")" ]; then ok "m22_result_line absent log -> empty"; else bad "m22_result_line absent log"; fi

section "10. m22_run_id uniqueness"
A="$(m22_run_id)"
B="$(m22_run_id)"
if [ -n "$A" ] && [ "$A" != "$B" ]; then ok "m22_run_id non-empty + unique"; else bad "m22_run_id unique"; fi

section "11. library-guard short-circuit (sourcing must not run main)"
if RUN_M22_RUNTIME_BASELINE_LIB=1 bash -c '. "$1"; [ -z "${PROD_PID:-}" ]' _ "$BASELINE" 2>/dev/null; then
    ok "baseline sources as a library without running main"
else
    bad "baseline library guard did not short-circuit"
fi
if RUN_M22_RUNTIME_REGRESSION_LIB=1 bash -c '. "$1"; [ -z "${PROD_PID:-}" ]' _ "$REGRESSION" 2>/dev/null; then
    ok "regression sources as a library without running main"
else
    bad "regression library guard did not short-circuit"
fi

echo
echo "RESULT: PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
