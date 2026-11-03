#!/usr/bin/env bash
# test_m17_touch_acceptance.sh -- host-side shell test for the M17.2 touch
# acceptance orchestration (scripts/run_m17_touch_acceptance.sh,
# scripts/test_touch_mode_control.sh, scripts/process_guard.sh).
#
# Verifies the M17.2 hardening WITHOUT touching the board or any real board binary:
#   * `bash -n` syntax of all three scripts;
#   * static source checks of the M17.2 behaviors (finite frames, stop+confirm
#     stale, PID/exe/socket verify, run_id + log offset, ctl-sock to both, control
#     socket fail-closed, strict single-line rec_scale, EXIT/INT/TERM trap);
#   * unit tests of process_guard.sh primitives -- including the four M17.2
#     scenarios: old-log false PASS, stale/old socket, orphan cleanup, custom socket;
#   * sourced-library unit tests of the rec_scale parse/resolve helpers (strict
#     single-line, multi-line rejected, override, cwd-first, fail-closed) and of
#     test_touch_mode_control.sh's arg parsing (custom socket / log offset / run id).
#
# Run from anywhere inside the package (WSL/Linux); exit 0 = ALL CHECKS PASSED.
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET="$SCRIPT_DIR/run_m17_touch_acceptance.sh"
TOUCH="$SCRIPT_DIR/test_touch_mode_control.sh"
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
for f in "$TARGET" "$TOUCH" "$GUARD"; do
    if bash -n "$f"; then ok "bash -n $(basename "$f")"; else bad "bash -n $(basename "$f")"; fi
done

section "1. finite default producer frames [M17.2 #1]"
if has 'PRODUCER_FRAMES=2000000'; then ok "default PRODUCER_FRAMES is finite (2000000)"; else bad "PRODUCER_FRAMES finite"; fi
if has 'PRODUCER_FRAMES=1000000000'; then bad "old effectively-infinite 1e9 default still present"; else ok "old 1e9 default removed"; fi
if has '--producer-frames='; then ok "--producer-frames= override accepted"; else bad "--producer-frames= override"; fi

section "2. stop + confirm stale services before start [M17.2 #2]"
if has 'stop_stale_services' && has 'confirm_services_stopped'; then ok "both stop/confirm helpers defined"; else bad "stop/confirm helpers"; fi
STOP_LINE="$(grep -nE '^[[:space:]]+stop_stale_services[[:space:]]*$' "$TARGET" | head -n1 | cut -d: -f1)"
CONF_LINE="$(grep -nF -- 'confirm_services_stopped || exit 2' "$TARGET" | head -n1 | cut -d: -f1)"
UI_LINE="$(grep -nF -- 'run_ui_live.sh"' "$TARGET" | head -n1 | cut -d: -f1)"
if [ -n "$STOP_LINE" ] && [ -n "$CONF_LINE" ] && [ -n "$UI_LINE" ] \
   && [ "$STOP_LINE" -lt "$CONF_LINE" ] && [ "$CONF_LINE" -lt "$UI_LINE" ]; then
    ok "order: stop_stale -> confirm -> start fresh UI ($STOP_LINE < $CONF_LINE < $UI_LINE)"
else
    bad "stop->confirm->UI order (stop=$STOP_LINE conf=$CONF_LINE ui=$UI_LINE)"
fi
if has 'find_pids_named'; then ok "stale detection uses find_pids_named"; else bad "find_pids_named used"; fi

section "3. PID / executable-path / socket-ownership verify [M17.2 #3]"
if has 'verify_ui' && has 'verify_producer'; then ok "verify_ui + verify_producer defined"; else bad "verify_ui/verify_producer"; fi
if has 'pid_matches_bin'; then ok "PID identity check (pid_matches_bin)"; else bad "pid_matches_bin"; fi
if has 'socket_served_by'; then ok "socket ownership check (socket_served_by)"; else bad "socket_served_by"; fi

section "4. unique run_id + log-offset result gating [M17.2 #4]"
if has 'run_id_new'; then ok "run_id generated via run_id_new"; else bad "run_id_new"; fi
if has 'LOG_OFFSET='; then ok "log offset captured"; else bad "LOG_OFFSET capture"; fi
if has '--log-offset="\$LOG_OFFSET"' && has '--run-id="\$RUN_ID"'; then ok "log-offset + run-id forwarded to touch test"; else bad "log-offset/run-id forwarding"; fi
if has 'log_offset_of'; then ok "offset computed via log_offset_of"; else bad "log_offset_of"; fi

section "5. custom control socket passed to BOTH UI and producer [M17.2 #5]"
if grep -qE 'run_ui_live\.sh".*--ctl-sock="\$CTL_SOCK"' "$TARGET"; then ok "UI started with --ctl-sock forwarded"; else bad "UI --ctl-sock"; fi
NCTL="$(grep -cF -- '--ctl-sock="$CTL_SOCK"' "$TARGET")"
if [ "$NCTL" -ge 2 ]; then ok "control socket forwarded to both UI and producer ($NCTL occurrences)"; else bad "ctl-sock to both ($NCTL occurrences)"; fi

section "6. control socket missing -> immediate fail-closed [M17.2 #6]"
if has 'control socket not served' "$TOUCH"; then ok "touch test fail-closed message on unserved control socket"; else bad "touch test fail-closed message"; fi
if has 'socket_served "\$CTL_SOCK"' "$TOUCH"; then ok "touch test checks control socket is SERVED"; else bad "touch test socket_served"; fi
if has 'exit 2' "$TOUCH"; then ok "touch test exits non-zero on missing socket"; else bad "touch test exit on missing socket"; fi

section "7. strict single-line rec_scale [M17.2 #7]"
if has 'multi-line rec_scale rejected'; then ok "multi-line rec_scale rejected message present"; else bad "multi-line rejection message"; fi
if has 'nonblank'; then ok "strict single-line (nonblank) check present"; else bad "nonblank check"; fi

section "8. EXIT/INT/TERM trap, only this run's PIDs [M17.2 #8]"
if has 'trap _cleanup EXIT'; then ok "EXIT trap -> _cleanup"; else bad "EXIT trap"; fi
if has "exit 130"; then ok "INT trap re-raises 130"; else bad "INT trap"; fi
if has "exit 143"; then ok "TERM trap re-raises 143"; else bad "TERM trap"; fi
if has 'stop_pid "\$PRODUCER_PID"' && has 'stop_pid "\$UI_PID"'; then ok "cleanup stops only this run's PIDs"; else bad "cleanup PIDs"; fi

section "9. process_guard unit tests: orphan cleanup (find/identity/stop)"
. "$GUARD"

SLEEP_PID=""
sleep 60 & SLEEP_PID=$!
if pid_alive "$SLEEP_PID"; then ok "pid_alive sees spawned process"; else bad "pid_alive spawned"; fi
if pid_alive 999999; then bad "pid_alive non-existent PID (should be dead)"; else ok "pid_alive rejects non-existent PID"; fi

if find_pids_named sleep | grep -qx "$SLEEP_PID"; then ok "find_pids_named locates spawned process by exe basename"; else bad "find_pids_named basename"; fi

EXE="$(pid_exe "$SLEEP_PID")"
if [ -n "$EXE" ]; then ok "pid_exe returns a path ($(basename "$EXE"))"; else bad "pid_exe empty"; fi
if pid_matches_bin "$SLEEP_PID" "$EXE"; then ok "pid_matches_bin accepts right exe"; else bad "pid_matches_bin right exe"; fi
if pid_matches_bin "$SLEEP_PID" "/definitely/not/the/right/binary"; then bad "pid_matches_bin accepts wrong exe"; else ok "pid_matches_bin rejects wrong exe"; fi
if pid_matches_bin 999999 "$EXE"; then bad "pid_matches_bin accepts dead PID"; else ok "pid_matches_bin rejects dead PID"; fi

stop_pid "$SLEEP_PID"
if pid_alive "$SLEEP_PID"; then bad "orphan cleanup: stop_pid left process alive"; else ok "orphan cleanup: stop_pid reaped the process"; fi
stop_pid "$SLEEP_PID"   # idempotent on an already-dead PID

section "10. old-log false PASS prevention (log_offset_of / tail_since) [M17.2 #4]"
TMP="$(mktemp -d)"
printf 'TOUCH_CONTROL_RESULT result=PASS commands_sent=5 commands_applied=5\n' > "$TMP/ui.log"
OFF="$(log_offset_of "$TMP/ui.log")"
printf 'TOUCH_CONTROL_RESULT result=FAIL commands_sent=0\n' >> "$TMP/ui.log"
if tail_since "$TMP/ui.log" "$OFF" | grep -q 'result=PASS'; then
    bad "old-log false PASS: post-offset tail still sees the OLD PASS line"
else
    ok "old-log false PASS prevented (old PASS excluded by offset)"
fi
if tail_since "$TMP/ui.log" "$OFF" | grep -q 'result=FAIL'; then ok "post-offset tail sees the NEW line"; else bad "post-offset tail misses new line"; fi
if tail_since "$TMP/ui.log" 0 | grep -q 'result=PASS'; then ok "offset 0 reads whole file (sanity)"; else bad "offset 0 whole file"; fi
if [ "$(log_offset_of "$TMP/absent.log")" = "0" ]; then ok "log_offset_of absent file -> 0"; else bad "log_offset_of absent file"; fi

section "11. old/stale socket rejection (socket_served / socket_served_by) [M17.2 #6]"
if socket_served "$TMP/does_not_exist.sock"; then bad "socket_served nonexistent path"; else ok "socket_served nonexistent -> not served"; fi
touch "$TMP/regular.sock"
if socket_served "$TMP/regular.sock"; then bad "socket_served regular file (not a socket)"; else ok "socket_served regular file -> not served"; fi

if command -v python3 >/dev/null 2>&1; then
    python3 - "$TMP/served.sock" <<'PY' &
import socket, sys, time
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.bind(sys.argv[1])
s.listen(1)
time.sleep(30)
PY
    SOCKPID=$!
    for _ in $(seq 1 50); do socket_served "$TMP/served.sock" && break; sleep 0.1; done
    if socket_served "$TMP/served.sock"; then
        ok "socket_served real served socket"
    else
        bad "socket_served real served socket (python3 present)"
    fi
    if socket_served_by "$TMP/served.sock" "$SOCKPID"; then ok "socket_served_by right pid"; else bad "socket_served_by right pid"; fi
    if socket_served_by "$TMP/served.sock" 999999; then bad "socket_served_by wrong pid accepted"; else ok "socket_served_by rejects wrong pid"; fi
    stop_pid "$SOCKPID"
    if [ -S "$TMP/served.sock" ]; then
        if socket_served "$TMP/served.sock"; then bad "stale socket node still reported served (old socket)"; else ok "stale socket node rejected (old socket)"; fi
    else
        echo "  (note: python unlinked the node on exit; stale-node sub-check skipped)"
    fi
else
    echo "  skip: python3 unavailable; served/stale socket sub-checks skipped"
fi

section "12. custom socket arg plumbing (test_touch_mode_control.sh library mode) [M17.2 #5]"
set +u
TOUCH_CONTROL_LIB=1 . "$TOUCH" --control-sock=/tmp/custom_ctl.sock --ui-log=/tmp/custom_ui.log \
    --log-offset=42 --run-id=run_xyz --timeout=9
set +e
set +o pipefail
set -u
if [ "${CTL_SOCK:-}" = "/tmp/custom_ctl.sock" ]; then ok "custom --control-sock honored"; else bad "custom --control-sock (got '${CTL_SOCK:-}')"; fi
if [ "${UI_LOG:-}" = "/tmp/custom_ui.log" ]; then ok "custom --ui-log honored"; else bad "custom --ui-log"; fi
if [ "${LOG_OFFSET:-}" = "42" ]; then ok "--log-offset honored"; else bad "--log-offset"; fi
if [ "${RUN_ID:-}" = "run_xyz" ]; then ok "--run-id honored"; else bad "--run-id"; fi
if [ "${TIMEOUT:-}" = "9" ]; then ok "--timeout honored"; else bad "--timeout"; fi
if declare -F await_result >/dev/null 2>&1; then ok "await_result() defined"; else bad "await_result()"; fi
if has '--control-sock=' "$TARGET" && has '--ui-sock=' "$TARGET"; then ok "orchestrator accepts --control-sock / --ui-sock overrides"; else bad "orchestrator sock overrides"; fi

section "13. run_id uniqueness"
A="$(run_id_new)"
B="$(run_id_new)"
if [ -n "$A" ] && [ "$A" != "$B" ]; then ok "run_id_new non-empty + unique"; else bad "run_id_new unique"; fi

section "14. rec_scale parse/resolve (sourced library) [M17.2 #7]"
set +u
RUN_M17_TOUCH_ACCEPTANCE_LIB=1 . "$TARGET"
set +e
set +o pipefail
set -u

printf 'rec_scale=1.365333\n' > "$TMP/good.txt"
GOT="$(parse_rec_scale_file "$TMP/good.txt")"
if [ "$GOT" = "1.365333" ]; then ok "parse good -> 1.365333"; else bad "parse good (got '$GOT')"; fi

if ! parse_rec_scale_file "$TMP/missing.txt" 2>/dev/null; then ok "parse missing -> fail"; else bad "parse missing"; fi
printf 'rec_scale=\n' > "$TMP/empty.txt"
if ! parse_rec_scale_file "$TMP/empty.txt" 2>/dev/null; then ok "parse empty value -> fail"; else bad "parse empty"; fi
printf 'rec_scale=0\n' > "$TMP/zero.txt"
if ! parse_rec_scale_file "$TMP/zero.txt" 2>/dev/null; then ok "parse zero -> fail (never 1.0)"; else bad "parse zero"; fi
printf 'rec_scale=-2.5\n' > "$TMP/neg.txt"
if ! parse_rec_scale_file "$TMP/neg.txt" 2>/dev/null; then ok "parse negative -> fail"; else bad "parse negative"; fi

# [M17.2 #7] multi-line MUST be rejected.
printf 'rec_scale=1.0\nrec_scale=2.0\n' > "$TMP/twoline.txt"
if parse_rec_scale_file "$TMP/twoline.txt" >/dev/null 2>&1; then bad "parse two rec_scale lines -> should FAIL (multi-line)"; else ok "parse two rec_scale lines -> fail (multi-line)"; fi
printf 'rec_scale=1.0\ngarbage\n' > "$TMP/garbageline.txt"
if parse_rec_scale_file "$TMP/garbageline.txt" >/dev/null 2>&1; then bad "parse trailing garbage line -> should FAIL"; else ok "parse trailing garbage line -> fail (strict single line)"; fi

# override
REC_SCALE_OVERRIDE="4.096"
if [ "$(resolve_rec_scale)" = "4.096" ]; then ok "resolve override -> 4.096"; else bad "resolve override"; fi
REC_SCALE_OVERRIDE="0"
if ! resolve_rec_scale 2>/dev/null; then ok "resolve override 0 -> fail"; else bad "resolve override 0"; fi
REC_SCALE_OVERRIDE=""

# cwd-first, then package root
mkdir -p "$TMP/cwd" "$TMP/root"
printf 'rec_scale=2.5\n' > "$TMP/cwd/rec_scale.txt"
printf 'rec_scale=9.9\n' > "$TMP/root/rec_scale.txt"
if [ "$(cd "$TMP/cwd" && ROOT="$TMP/root" resolve_rec_scale)" = "2.5" ]; then ok "resolve prefers current-dir (2.5 over 9.9)"; else bad "resolve cwd-first"; fi
rm -f "$TMP/cwd/rec_scale.txt"
if [ "$(cd "$TMP/cwd" && ROOT="$TMP/root" resolve_rec_scale)" = "9.9" ]; then ok "resolve falls back to package root (9.9)"; else bad "resolve root fallback"; fi

mkdir -p "$TMP/emptyroot"
if (cd "$TMP/cwd" && ROOT="$TMP/emptyroot" && resolve_rec_scale) >/dev/null 2>&1; then
    bad "resolve missing everywhere -> should fail"
else
    ok "resolve missing everywhere -> fail"
fi

rm -rf "$TMP"

echo
echo "RESULT: PASS=$PASS FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
