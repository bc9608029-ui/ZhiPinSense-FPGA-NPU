#!/usr/bin/env bash
# test_m18_sw1_touch_acceptance.sh -- host-side shell test for the M18-SW1 Task C
# single-verdict touch acceptance orchestration
# (scripts/run_m18_sw1_touch_acceptance.sh, scripts/process_guard.sh).
#
# Verifies, WITHOUT touching the board or any real board binary, that the M18-SW1
# flow eliminates the same-round FAIL-then-PASS race and is fail-closed:
#
#   * `bash -n` syntax of the three scripts;
#   * static checks: FINALIZE_TEST token, EXACTLY ONE verdict echo, --run-id
#     forwarded to the UI, result gated by BOTH byte-offset AND run_id, UI-first
#     start order, LOG_OFFSET captured after verify_ui, stop_pid_if_matches (never
#     bare stop_pid on this run's PIDs), UI-early-exit / Gate9-early-exit detection,
#     finite producer frames, strict single-line rec_scale, EXIT/INT/TERM trap;
#   * sourced-library functional tests of match_result (offset + run_id gating: a
#     stale PASS or a PASS of a different run_id is never accepted) and
#     classify_result (PASS/FAIL mapping);
#   * sourced-library unit tests of parse_rec_scale_file / resolve_rec_scale and of
#     the process_guard primitives (old-log false PASS, PID identity, stop_pid_if_matches).
#
# Run from anywhere inside the package (WSL/Linux); exit 0 = ALL CHECKS PASSED.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$SCRIPT_DIR/run_m18_sw1_touch_acceptance.sh"
UI_LIVE="$SCRIPT_DIR/run_ui_live.sh"
GUARD="$SCRIPT_DIR/process_guard.sh"
PASS=0
FAIL=0

ok()  { PASS=$((PASS+1)); echo "  ok  $1"; }
bad() { FAIL=$((FAIL+1)); echo "  FAIL $1"; }

section() { echo "== $1 =="; }

# grep the target (default) or a given file; returns 0 if pattern present.
has() { grep -qE -- "$1" "${2:-$TARGET}"; }

# line number of first match (or empty).
lineno() { grep -nE -- "$1" "${2:-$TARGET}" | head -n 1 | cut -d: -f1; }

section "0. syntax: bash -n"
for f in "$TARGET" "$UI_LIVE" "$GUARD"; do
    if bash -n "$f"; then ok "bash -n $(basename "$f")"; else bad "bash -n $(basename "$f")"; fi
done

section "1. explicit FINALIZE_TEST token (user confirms done)"
if has 'FINALIZE_TEST'; then ok "FINALIZE_TEST token present"; else bad "FINALIZE_TEST token"; fi
if grep -qF -- 'line" = "FINALIZE_TEST"' "$TARGET"; then ok "FINALIZE_TEST matched as an exact line"; else bad "FINALIZE_TEST exact-line match"; fi

section "2. EXACTLY ONE verdict echo (no second opposite result)"
NV="$(grep -c 'echo "M18_SW1_TOUCH_ACCEPTANCE result=' "$TARGET")"
if [ "$NV" -eq 1 ]; then ok "exactly one verdict echo ($NV)"; else bad "single verdict echo (got $NV)"; fi
if has 'result=\$verdict'; then ok "verdict computed from a variable (PASS/FAIL)"; else bad "verdict from variable"; fi
NM="$(grep -c '\$(match_result' "$TARGET")"
if [ "$NM" -eq 1 ]; then ok "match_result read exactly once before the verdict ($NM)"; else bad "match_result read once (got $NM)"; fi

section "3. result gated by BOTH byte-offset AND run_id [Task C #9/#12]"
if has 'tail_since' && has 'grep -F "run_id=\$rid"'; then ok "match_result gates on offset (tail_since) AND run_id"; else bad "offset+run_id gating in match_result"; fi
if has '--run-id="\$RUN_ID"' && grep -qF -- 'run_ui_live.sh" --sock="$UI_SOCK" --ctl-sock="$CTL_SOCK" --run-id="$RUN_ID"' "$TARGET"; then
    ok "--run-id forwarded to the UI so its result line is tagged"
else
    bad "--run-id forwarding to UI"
fi

section "4. UI-first start order + LOG_OFFSET after verify_ui"
UI_LINE="$(lineno 'run_ui_live.sh" --sock="\$UI_SOCK"')"
VERIFY_UI_LINE="$(lineno 'verify_ui \|\| exit 2')"
LOG_OFFSET_LINE="$(lineno 'LOG_OFFSET="\$\(log_offset_of "\$UI_LOG"\)"')"
PROD_LINE="$(lineno 'run_gate9_ui.sh"')"
if [ -n "$UI_LINE" ] && [ -n "$VERIFY_UI_LINE" ] && [ -n "$LOG_OFFSET_LINE" ] && [ -n "$PROD_LINE" ] \
   && [ "$UI_LINE" -lt "$VERIFY_UI_LINE" ] && [ "$VERIFY_UI_LINE" -lt "$LOG_OFFSET_LINE" ] \
   && [ "$LOG_OFFSET_LINE" -lt "$PROD_LINE" ]; then
    ok "order: start UI < verify_ui < LOG_OFFSET < start producer ($UI_LINE < $VERIFY_UI_LINE < $LOG_OFFSET_LINE < $PROD_LINE)"
else
    bad "UI->verify->offset->producer order (ui=$UI_LINE verify=$VERIFY_UI_LINE off=$LOG_OFFSET_LINE prod=$PROD_LINE)"
fi

section "5. stop + confirm stale services before start"
if has 'stop_stale_services' && has 'confirm_services_stopped'; then ok "stop/confirm helpers defined"; else bad "stop/confirm helpers"; fi
STOP_LINE="$(lineno '^[[:space:]]+stop_stale_services[[:space:]]*$')"
CONF_LINE="$(lineno 'confirm_services_stopped \|\| exit 2')"
if [ -n "$STOP_LINE" ] && [ -n "$CONF_LINE" ] && [ "$STOP_LINE" -lt "$CONF_LINE" ] && [ "$CONF_LINE" -lt "$UI_LINE" ]; then
    ok "order: stop_stale < confirm < start UI"
else
    bad "stop->confirm->UI order"
fi

section "6. PID identity + socket ownership verification"
if has 'verify_ui' && has 'verify_producer'; then ok "verify_ui + verify_producer defined"; else bad "verify_ui/verify_producer"; fi
if has 'pid_matches_bin' && has 'socket_served_by'; then ok "pid_matches_bin + socket_served_by"; else bad "pid/socket identity checks"; fi

section "7. fail-closed: UI-early-exit + Gate9-early-exit during finalize wait"
if has 'UI exited early'; then ok "UI-early-exit detection"; else bad "UI-early-exit"; fi
if has 'producer exited early'; then ok "Gate9-early-exit detection (pid + control socket)"; else bad "Gate9-early-exit"; fi
if has 'no FINALIZE_TEST within'; then ok "FINALIZE_TEST timeout -> fail-closed"; else bad "FINALIZE_TEST timeout"; fi

section "8. finite producer frames + strict single-line rec_scale"
if has 'PRODUCER_FRAMES=50000'; then ok "default producer frames finite (50000)"; else bad "producer frames finite"; fi
if has 'PRODUCER_FRAMES=1000000000'; then bad "old 1e9 default still present"; else ok "old 1e9 default removed"; fi
if has 'multi-line rec_scale rejected'; then ok "multi-line rec_scale rejected"; else bad "multi-line rec_scale"; fi

section "9. EXIT/INT/TERM trap + identity re-checked cleanup"
if has 'trap _cleanup EXIT'; then ok "EXIT trap -> _cleanup"; else bad "EXIT trap"; fi
if has 'exit 130' && has 'exit 143'; then ok "INT/TERM re-raise 130/143"; else bad "INT/TERM trap"; fi
if has 'stop_pid_if_matches "\$UI_PID"' && has 'stop_pid_if_matches "\$PRODUCER_PID"'; then
    ok "cleanup uses stop_pid_if_matches (identity re-checked)"
else
    bad "cleanup stop_pid_if_matches"
fi
if ! grep -qE 'stop_pid "\$UI_PID"|stop_pid "\$PRODUCER_PID"' "$TARGET"; then
    ok "no bare stop_pid on this run's PIDs"
else
    bad "bare stop_pid still used in cleanup"
fi

section "10. sourced-library: match_result offset + run_id gating"
set +u
RUN_M18_SW1_TOUCH_ACCEPTANCE_LIB=1 . "$TARGET"
set +e
set +o pipefail
set -u

TMP="$(mktemp -d)"

# log: a STALE PASS (previous run, before offset), then THIS run's FAIL (after offset).
printf 'TOUCH_CONTROL_RESULT result=PASS commands_sent=5 commands_applied=5 run_id=old_run\n' > "$TMP/ui.log"
OFF="$(log_offset_of "$TMP/ui.log")"
printf 'TOUCH_CONTROL_RESULT result=FAIL commands_sent=1 commands_applied=0 run_id=our_run\n' >> "$TMP/ui.log"
GOT="$(match_result "$TMP/ui.log" "$OFF" "our_run")"
if [ -n "$GOT" ] && echo "$GOT" | grep -q 'result=FAIL'; then
    ok "match_result: post-offset result returned (stale pre-offset PASS excluded)"
else
    bad "match_result post-offset (got '$GOT')"
fi
if echo "$GOT" | grep -q 'result=PASS'; then bad "match_result: stale PASS leaked"; else ok "match_result: no stale PASS leaked"; fi

# run_id gating: a PASS tagged a DIFFERENT run_id must never be accepted.
printf 'TOUCH_CONTROL_RESULT result=PASS commands_sent=5 commands_applied=5 run_id=other\n' >> "$TMP/ui.log"
if match_result "$TMP/ui.log" 0 "our_run" | grep -q 'result=PASS'; then
    bad "match_result: PASS of a different run_id accepted"
else
    ok "match_result: PASS-of-other-run_id rejected"
fi
if match_result "$TMP/ui.log" 0 "our_run" | grep -q 'result=FAIL'; then
    ok "match_result: this run's FAIL still returned despite a foreign PASS"
else
    bad "match_result: this run's line lost"
fi

# offset 0 reads the whole file (sanity).
if match_result "$TMP/ui.log" 0 "old_run" | grep -q 'result=PASS'; then
    ok "match_result offset 0 sees the whole file"
else
    bad "match_result offset 0"
fi

# no result for this run_id -> empty.
if [ -z "$(match_result "$TMP/ui.log" "$OFF" "no_such_run")" ]; then
    ok "match_result: unknown run_id -> empty (fail-closed)"
else
    bad "match_result unknown run_id"
fi

section "11. sourced-library: classify_result mapping"
if [ "$(classify_result 'TOUCH_CONTROL_RESULT result=PASS x=1')" = "PASS" ]; then ok "classify_result PASS"; else bad "classify_result PASS"; fi
if classify_result 'TOUCH_CONTROL_RESULT result=PASS x=1' >/dev/null; then ok "classify_result PASS returns 0"; else bad "classify_result PASS rc"; fi
if [ "$(classify_result 'TOUCH_CONTROL_RESULT result=FAIL x=1')" = "FAIL" ]; then ok "classify_result FAIL"; else bad "classify_result FAIL"; fi
if classify_result 'TOUCH_CONTROL_RESULT result=FAIL x=1' >/dev/null; then bad "classify_result FAIL returns non-zero"; else ok "classify_result FAIL returns non-zero"; fi

section "12. sourced-library: rec_scale parse/resolve (strict single line)"
printf 'rec_scale=1.365333\n' > "$TMP/good.txt"
if [ "$(parse_rec_scale_file "$TMP/good.txt")" = "1.365333" ]; then ok "parse good -> 1.365333"; else bad "parse good"; fi
if ! parse_rec_scale_file "$TMP/missing.txt" 2>/dev/null; then ok "parse missing -> fail"; else bad "parse missing"; fi
printf 'rec_scale=\n' > "$TMP/empty.txt"
if ! parse_rec_scale_file "$TMP/empty.txt" 2>/dev/null; then ok "parse empty value -> fail"; else bad "parse empty"; fi
printf 'rec_scale=0\n' > "$TMP/zero.txt"
if ! parse_rec_scale_file "$TMP/zero.txt" 2>/dev/null; then ok "parse zero -> fail (never 1.0)"; else bad "parse zero"; fi
printf 'rec_scale=-2.5\n' > "$TMP/neg.txt"
if ! parse_rec_scale_file "$TMP/neg.txt" 2>/dev/null; then ok "parse negative -> fail"; else bad "parse negative"; fi
printf 'rec_scale=1.0\nrec_scale=2.0\n' > "$TMP/twoline.txt"
if parse_rec_scale_file "$TMP/twoline.txt" >/dev/null 2>&1; then bad "parse two lines -> should FAIL"; else ok "parse two rec_scale lines -> fail (multi-line)"; fi

REC_SCALE_OVERRIDE="4.096"
if [ "$(resolve_rec_scale)" = "4.096" ]; then ok "resolve override -> 4.096"; else bad "resolve override"; fi
REC_SCALE_OVERRIDE="0"
if ! resolve_rec_scale 2>/dev/null; then ok "resolve override 0 -> fail"; else bad "resolve override 0"; fi
REC_SCALE_OVERRIDE=""

section "13. sourced-library: process_guard primitives"
sleep 60 & SLP=$!
if pid_alive "$SLP"; then ok "pid_alive spawned"; else bad "pid_alive spawned"; fi
if pid_alive 999999; then bad "pid_alive non-existent"; else ok "pid_alive rejects non-existent"; fi
EXE="$(pid_exe "$SLP")"
if [ -n "$EXE" ]; then ok "pid_exe returns a path"; else bad "pid_exe empty"; fi
if pid_matches_bin "$SLP" "$EXE"; then ok "pid_matches_bin right exe"; else bad "pid_matches_bin right exe"; fi
if pid_matches_bin "$SLP" "/definitely/not/this/binary"; then bad "pid_matches_bin wrong exe accepted"; else ok "pid_matches_bin wrong exe rejected"; fi
stop_pid_if_matches "$SLP" "/definitely/not/this/binary"
if pid_alive "$SLP"; then ok "stop_pid_if_matches spares wrong-exe PID"; else bad "stop_pid_if_matches killed wrong-exe PID"; fi
stop_pid_if_matches "$SLP" "$EXE"
if pid_alive "$SLP"; then bad "stop_pid_if_matches failed to kill matching PID"; else ok "stop_pid_if_matches kills matching PID"; fi

# old-log false PASS: a result appended BEFORE the offset must not be seen.
printf 'TOUCH_CONTROL_RESULT result=PASS run_id=old\n' > "$TMP/old.log"
O2="$(log_offset_of "$TMP/old.log")"
printf 'TOUCH_CONTROL_RESULT result=FAIL run_id=new\n' >> "$TMP/old.log"
if tail_since "$TMP/old.log" "$O2" | grep -q 'result=PASS'; then
    bad "old-log false PASS: post-offset tail sees the OLD PASS"
else
    ok "old-log false PASS prevented (offset excludes old line)"
fi
if tail_since "$TMP/old.log" "$O2" | grep -q 'result=FAIL'; then ok "post-offset tail sees the new line"; else bad "post-offset tail misses new line"; fi
if [ "$(log_offset_of "$TMP/absent.log")" = "0" ]; then ok "log_offset_of absent -> 0"; else bad "log_offset_of absent"; fi

section "14. run_id uniqueness"
A="$(run_id_new)"
B="$(run_id_new)"
if [ -n "$A" ] && [ "$A" != "$B" ]; then ok "run_id_new non-empty + unique"; else bad "run_id_new unique"; fi

rm -rf "$TMP"

echo
echo "RESULT: PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
