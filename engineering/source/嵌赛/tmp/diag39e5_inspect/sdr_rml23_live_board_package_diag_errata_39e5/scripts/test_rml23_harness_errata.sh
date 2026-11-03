#!/usr/bin/env bash
# test_rml23_harness_errata.sh -- host-side regression for the RML23 (M29 F5)
# harness PID/wait ownership errata (the M22.1 caller-variable launcher fix ported
# to the RML23 scripts).  Runs on any Linux host (WSL/board) and does NOT touch the
# board or the real Gate 9 binary: it uses a tiny compiled fake that mirrors the
# Gate 9 M22 instrumentation (one `M22_RUNTIME_RESULT result=...` line + a
# `--perf-file` JSON + an exit code).
#
# It REPRODUCES the old command-substitution failure (`wait: ... is not a child of
# this shell`) and then PROVES the new `printf -v` launcher fixes it -- so the fix is
# verified by behaviour, not by string substitution.  Coverage (M22.1 §三.3 ported,
# plus RML23 script-structure checks):
#
#   1. the launched PID is a DIRECT child of this shell (PPid == $$);
#   2. `wait` succeeds without "not a child";
#   3. child exit codes 0 / 1 / 2 propagate through `wait`;
#   4. an early exit that never emits M22_RUNTIME_RESULT is judged PREP_FAIL;
#   5. a missing/empty perf JSON fails the verdict;
#   6. cleanup (stop_pid_if_matches) never kills a stale PID or a wrong executable,
#      but does kill THIS run's PID when the identity matches;
#   7. every caller (test_live_1000/10000 + run_m22_runtime_baseline/regression)
#      uses the caller-variable launcher (no command substitution);
#   8. `bash -n` on all five scripts passes;
#   9. RML23 test_live script-structure checks (single verdict line, fail-closed
#      exit 0/1/2, cleanup identity, RF/UI source wiring, library guards).
#
# Exit: 0 = all checks passed.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HARNESS="$SCRIPT_DIR/m22_harness.sh"
PROCESS_GUARD="$SCRIPT_DIR/process_guard.sh"
LIVE1000="$SCRIPT_DIR/test_live_1000_frames.sh"
LIVE10000="$SCRIPT_DIR/test_live_10000_frames.sh"
BASELINE="$SCRIPT_DIR/run_m22_runtime_baseline.sh"
REGRESSION="$SCRIPT_DIR/run_m22_runtime_regression.sh"
PASS=0
FAIL=0

ok()  { PASS=$((PASS+1)); echo "  ok  $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL $1"; }
section() { echo "== $1 =="; }

# ---- a tiny compiled fake Gate 9 ----------------------------------------------
# Compiling (rather than a shell script) keeps /proc/PID/exe == the fake binary path,
# which is what stop_pid_if_matches's executable-identity check needs.  Mirrors the
# real binary's observable contract: result line, perf JSON, exit code.
TMP="$(mktemp -d)"
FAKE_SRC="$TMP/fake_gate9.c"
cat > "$FAKE_SRC" <<'EOF'
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <unistd.h>
int main(int argc, char** argv) {
    const char* result = "PASS";
    const char* perf = 0;
    int exitcode = 0, perf_mode = 0, no_result = 0, sleep_s = 0;
    for (int i = 1; i < argc; ++i) {
        if      (!strncmp(argv[i], "--result=",    9))  result   = argv[i] + 9;
        else if (!strncmp(argv[i], "--exit=",      7))  exitcode = atoi(argv[i] + 7);
        else if (!strncmp(argv[i], "--perf-file=", 12)) perf     = argv[i] + 12;
        else if (!strncmp(argv[i], "--perf-mode=", 12)) perf_mode = atoi(argv[i] + 12);
        else if (!strcmp(argv[i], "--no-result"))       no_result = 1;
        else if (!strncmp(argv[i], "--sleep=",     8))  sleep_s   = atoi(argv[i] + 8);
    }
    if (sleep_s > 0) sleep((unsigned)sleep_s);
    if (perf) {
        FILE* f = fopen(perf, "w");
        if (f) { if (perf_mode == 0) fputs("{\"ok\":true}\n", f); fclose(f); }
    }
    if (!no_result) printf("M22_RUNTIME_RESULT result=%s phase=test\n", result);
    fflush(stdout);
    return exitcode;
}
EOF

trap 'rm -rf "$TMP"' EXIT
FAKE="$TMP/fake_gate9"
if ${CC:-gcc} -O2 -Wall -Wextra -o "$FAKE" "$FAKE_SRC" 2>"$TMP/cc.err"; then
    ok "fake gate9 compiled"
else
    bad "fake gate9 compile failed"; cat "$TMP/cc.err" >&2; exit 1
fi

# ---- the OLD (buggy) launcher, kept verbatim to reproduce the failure ---------
old_run_gate9_captured() {
    local logfile="$1" bin="$2"
    shift 2
    "$bin" "$@" >"$logfile" 2>&1 &
    printf '%s\n' "$!"
}

# ppid of a PID from /proc (no ps dependency, matching process_guard.sh).
ppid_of() { awk '/^PPid:/{print $2}' "/proc/$1/status" 2>/dev/null || true; }

section "0. syntax: bash -n"
for f in "$HARNESS" "$PROCESS_GUARD" "$LIVE1000" "$LIVE10000" "$BASELINE" "$REGRESSION"; do
    if bash -n "$f"; then ok "bash -n $(basename "$f")"; else bad "bash -n $(basename "$f")"; fi
done

section "1. OLD launcher reproduces the 'not a child' failure"
OLDPID="$(old_run_gate9_captured "$TMP/old.log" "$FAKE" --result=PASS)"
wait "$OLDPID" 2>"$TMP/old_wait.err"
if grep -q 'not a child' "$TMP/old_wait.err"; then
    ok "old launcher: wait reports 'not a child of this shell'"
else
    bad "old launcher: expected 'not a child' (got: $(cat "$TMP/old_wait.err"))"
fi
if [ "$(ppid_of "$OLDPID")" != "$$" ]; then
    ok "old launcher: PID is NOT a child of this shell (orphaned by the subshell)"
else
    bad "old launcher: PID unexpectedly still a child of this shell"
fi

# Load the NEW harness under test.
. "$HARNESS"
. "$PROCESS_GUARD"

section "2. NEW launcher: PID is a direct child and wait succeeds"
PROD_PID=""
run_gate9_captured PROD_PID "$TMP/new.log" "$FAKE" --result=PASS --sleep=2
if [ "$(ppid_of "$PROD_PID")" = "$$" ]; then
    ok "new launcher: PID $PROD_PID is a direct child of this shell (PPid=$$)"
else
    bad "new launcher: PPid=$(ppid_of "$PROD_PID") != $$"
fi
wait "$PROD_PID" 2>"$TMP/new_wait.err"
rc=$?
if [ "$rc" -eq 0 ] && ! grep -q 'not a child' "$TMP/new_wait.err"; then
    ok "new launcher: wait succeeded (rc=0, no 'not a child')"
else
    bad "new launcher: wait failed (rc=$rc; $(cat "$TMP/new_wait.err"))"
fi

section "3. exit code 0 / 1 / 2 propagate through wait"
for code in 0 1 2; do
    PROD_PID=""
    run_gate9_captured PROD_PID "$TMP/e$code.log" "$FAKE" --result=PASS --exit="$code"
    wait "$PROD_PID" 2>/dev/null
    got=$?
    if [ "$got" -eq "$code" ]; then ok "exit $code propagated"; else bad "exit $code -> got $got"; fi
done

section "4. early exit with no result line -> PREP_FAIL"
PROD_PID=""
run_gate9_captured PROD_PID "$TMP/early.log" "$FAKE" --result=PASS --no-result --exit=0
wait "$PROD_PID" 2>/dev/null
rc=$?
line="$(m22_result_line "$TMP/early.log")"
verdict="$(m22_run_verdict "$rc" "$line" "1")"
if [ "$verdict" = "PREP_FAIL" ]; then ok "no result line -> PREP_FAIL"; else bad "no result line -> $verdict"; fi

section "5. missing / empty perf JSON -> FAIL"
# missing perf file
PROD_PID=""
run_gate9_captured PROD_PID "$TMP/pfmiss.log" "$FAKE" --result=PASS --perf-mode=2
wait "$PROD_PID" 2>/dev/null
rc=$?
line="$(m22_result_line "$TMP/pfmiss.log")"
verdict="$(m22_run_verdict "$rc" "$line" "$(m22_perf_nonempty "$TMP/pfmiss.json")")"
if [ "$verdict" = "FAIL" ]; then ok "missing perf -> FAIL"; else bad "missing perf -> $verdict"; fi
# empty perf file
PROD_PID=""
run_gate9_captured PROD_PID "$TMP/pfempty.log" "$FAKE" --result=PASS --perf-file="$TMP/pfempty.json" --perf-mode=1
wait "$PROD_PID" 2>/dev/null
rc=$?
line="$(m22_result_line "$TMP/pfempty.log")"
verdict="$(m22_run_verdict "$rc" "$line" "$(m22_perf_nonempty "$TMP/pfempty.json")")"
if [ "$verdict" = "FAIL" ]; then ok "empty perf -> FAIL"; else bad "empty perf -> $verdict"; fi

section "6. cleanup identity: stale PID and wrong exe are never killed"
# stale (not-alive) PID must be a no-op
stop_pid_if_matches 999999999 "$FAKE" || true
ok "stale PID is a no-op for stop_pid_if_matches"
# wrong executable: a decoy sleep claiming to be the fake must NOT be killed
sleep 30 & decoy=$!
stop_pid_if_matches "$decoy" "$FAKE"
if pid_alive "$decoy"; then
    ok "wrong-exe PID not killed"; kill "$decoy" 2>/dev/null || true
else
    bad "wrong-exe PID was killed"
fi
# correct executable: THIS run's fake must be killed
PROD_PID=""
run_gate9_captured PROD_PID "$TMP/slow.log" "$FAKE" --result=PASS --sleep=30
stop_pid_if_matches "$PROD_PID" "$FAKE"
if ! pid_alive "$PROD_PID"; then ok "matching-exe PID killed"; else bad "matching-exe PID survived"; kill "$PROD_PID" 2>/dev/null || true; fi

section "7. every caller uses the caller-variable launcher (no command substitution)"
for s in "$LIVE1000" "$LIVE10000" "$BASELINE" "$REGRESSION"; do
    n="$(basename "$s")"
    if grep -q 'run_gate9_captured PROD_PID ' "$s"; then
        ok "$n: launcher writes into PROD_PID by name"
    else
        bad "$n: launcher does not use the caller-variable form"
    fi
    if ! grep -q 'PROD_PID="\$(run_gate9_captured' "$s"; then
        ok "$n: no command-substitution PID capture"
    else
        bad "$n: still uses command-substitution PID capture"
    fi
done

section "8. RML23 test_live script structure (single verdict + fail-closed exit)"
for s in "$LIVE1000" "$LIVE10000"; do
    n="$(basename "$s")"
    tag="$([ "$n" = "test_live_1000_frames.sh" ] && echo RML23_TEST_LIVE || echo RML23_TEST_LIVE_LONG)"
    # exactly ONE final verdict echo
    c=$(grep -c "echo \"$tag result=" "$s")
    [ "$c" -eq 1 ] && ok "$n: exactly one verdict echo ($tag)" || bad "$n: verdict echo count=$c"
    # exit 0/1/2 propagated via case on the verdict
    grep -q 'PASS) return 0' "$s" && grep -q 'PREP_FAIL) return 2' "$s" && grep -q '\*) return 1' "$s" \
        && ok "$n: exit 0/1/2 propagated via case" || bad "$n: exit 0/1/2 propagation"
    # fail-closed: no result line -> PREP_FAIL with log tail
    grep -q 'no M22_RUNTIME_RESULT line' "$s" && ok "$n: fail-closed on missing result line" \
        || bad "$n: missing-result fail-closed"
    # perf JSON is a PASS precondition
    grep -q 'm22_perf_nonempty' "$s" && ok "$n: perf non-empty precondition" || bad "$n: perf precondition"
    # cleanup identity
    grep -q 'stop_pid_if_matches "\$PROD_PID" "\$BIN"' "$s" && ok "$n: cleanup stop_pid_if_matches (identity)" \
        || bad "$n: cleanup identity"
    # traps
    grep -q 'trap _cleanup EXIT' "$s" && ok "$n: EXIT trap" || bad "$n: EXIT trap"
    grep -q 'exit 130' "$s" && grep -q 'exit 143' "$s" && ok "$n: INT/TERM re-raise" || bad "$n: INT/TERM"
    # sources + library guard
    grep -q 'common_rml23.sh' "$s" && grep -q 'process_guard.sh' "$s" && grep -q 'm22_harness.sh' "$s" \
        && ok "$n: sources common_rml23/process_guard/m22_harness" || bad "$n: sources"
    grep -q '_LIB:-0' "$s" && ok "$n: library guard present" || bad "$n: library guard"
    # --perf-file forwarded
    grep -q -- '--perf-file="\$PERF"' "$s" && ok "$n: forwards --perf-file" || bad "$n: --perf-file"
done

section "9. RML23 test_live defaults (frames + phase)"
grep -q 'FRAMES=1000' "$LIVE1000" && ok "test_live_1000 default FRAMES=1000" || bad "test_live_1000 FRAMES=1000"
grep -q 'FRAMES=10000' "$LIVE10000" && ok "test_live_10000 default FRAMES=10000" || bad "test_live_10000 FRAMES=10000"
grep -q 'PHASE="digital"' "$LIVE1000" && ok "test_live_1000 default phase=digital" || bad "test_live_1000 phase"

echo
echo "RESULT: PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
