#!/usr/bin/env bash
# test_mode_control_runtime.sh -- Task E board test: control-channel real-time
# responsiveness + UI state synchronisation.
#
# Proves, on the board (NOT by lengthening a client timeout), that the Gate 9
# producer's reverse control channel decouples command RECEPTION from APPLICATION:
#
#   * STATUS   is answered at once (read-only, answered from the atomic snapshot,
#              never queued -- responsive even while the producer is in a libiio call);
#   * STOP     -> "OK accepted command_id=N STOP" within <=500 ms, then
#                 applied_running=0 (the STOP really reaches the screen);
#   * START    -> applied_running=1;
#   * SET_MODE BAND_SCAN -> applied_mode=BAND_SCAN, then SET_MODE FIXED -> FIXED
#                 (BAND SCAN is interruptible by a later SET_MODE);
#   * convergence: control_queue_depth=0 and requested_* == applied_* at the end.
#
# Prereq: the Gate 9 producer is running with its control server on
# /run/sdr_amr_control.sock (e.g. launched via run_gate9_ui.sh).
#
#   ./test_mode_control_runtime.sh [--sock=/run/sdr_amr_control.sock]
#
# Exit 0 = every assertion passed; non-zero = a command was rejected, timed out,
# or the producer never reached the requested state.
set -euo pipefail
. "$(dirname "$0")/common.sh"

BIN="$(require_bin board_mode_ctl)"
SOCK="/run/sdr_amr_control.sock"
for a in "$@"; do
    case "$a" in
        --sock=*) SOCK="${a#--sock=}" ;;
    esac
done

POLL_SEC="${POLL_SEC:-0.1}"
APPLY_MAX_TRIES="${APPLY_MAX_TRIES:-20}"   # 20 * 0.1 s = 2 s apply budget
ACCEPT_MAX_MS="${ACCEPT_MAX_MS:-500}"

fail() { echo "MODE_CONTROL_FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# Send one command to the control socket (prints the reply, exit code mirrors it).
ctl() { "$BIN" --sock="$SOCK" "$@"; }

# Extract a key=value token from a reply line (pure shell, no grep/sed).
field() {
    local reply="$1" name="$2" tok
    for tok in $reply; do
        case "$tok" in
            "$name="*) printf '%s' "${tok#"$name"=}"; return 0 ;;
        esac
    done
    return 1
}

status() { ctl STATUS 2>/dev/null; }

# Millisecond clock (GNU date; the board userland already uses GNU coreutils).
now_ms() { date +%s%3N; }

# Poll STATUS until field NAME == VALUE, else fail after the apply budget.
wait_applied() {
    local name="$1" value="$2" i=0 reply v
    while [ "$i" -lt "$APPLY_MAX_TRIES" ]; do
        i=$(( i + 1 ))
        reply="$(status)" || fail "STATUS lost while waiting for $name=$value"
        v="$(field "$reply" "$name")" || fail "STATUS missing field $name (reply: $reply)"
        if [ "$v" = "$value" ]; then
            pass "$name=$value (applied within $(( i * 100 )) ms)"
            return 0
        fi
        sleep "$POLL_SEC"
    done
    fail "timeout: $name still != $value (last=$v reply=$reply)"
}

banner "Task E: control-channel real-time + UI state synchronisation"

# 1. STATUS reachable + responsive.
if ! status >/dev/null; then
    fail "STATUS unreachable -- is the Gate 9 producer running on $SOCK ?"
fi
pass "STATUS responsive"

# 2. STOP: ACCEPTED <=500 ms, then applied_running=0.
t0="$(now_ms)"; acc="$(ctl STOP)" || fail "STOP rejected: $acc"
t1="$(now_ms)"
case "$acc" in
    "OK accepted command_id="*) ;;
    *) fail "STOP not accepted: $acc" ;;
esac
lat=$(( t1 - t0 ))
[ "$lat" -le "$ACCEPT_MAX_MS" ] || fail "STOP accept latency ${lat}ms > ${ACCEPT_MAX_MS}ms"
pass "STOP accepted in ${lat}ms"
wait_applied applied_running 0

# 3. START -> applied_running=1.
acc="$(ctl START)" || fail "START rejected: $acc"
pass "START accepted"
wait_applied applied_running 1

# 4. SET_MODE BAND_SCAN -> applied_mode=BAND_SCAN.
acc="$(ctl SET_MODE BAND_SCAN)" || fail "SET_MODE BAND_SCAN rejected: $acc"
pass "SET_MODE BAND_SCAN accepted"
wait_applied applied_mode BAND_SCAN

# 5. SET_MODE FIXED -> applied_mode=FIXED (BAND SCAN is interruptible).
acc="$(ctl SET_MODE FIXED)" || fail "SET_MODE FIXED rejected: $acc"
pass "SET_MODE FIXED accepted"
wait_applied applied_mode FIXED

# 6. Convergence: queue empty, requested == applied.
final="$(status)" || fail "final STATUS lost"
req_mode="$(field "$final" requested_mode)"
app_mode="$(field "$final" applied_mode)"
req_run="$(field "$final" requested_running)"
app_run="$(field "$final" applied_running)"
qd="$(field "$final" control_queue_depth)"
[ "$req_mode" = "$app_mode" ] || fail "requested_mode=$req_mode != applied_mode=$app_mode"
[ "$req_run" = "$app_run" ]   || fail "requested_running=$req_run != applied_running=$app_run"
[ "$qd" = "0" ]               || fail "control_queue_depth=$qd != 0"
pass "converged: queue_depth=0 requested==applied (mode=$app_mode running=$app_run)"

echo "MODE_CONTROL_RUNTIME_PASS sock=$SOCK"
