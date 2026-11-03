#!/usr/bin/env bash
# start_all_rml23.sh -- one-click bring-up of the RML23 23-class LIVE chain: the
# UI server (board_ui_live_rml23) FIRST, then the Gate 9 RML23 producer
# (board_gate9_full_chain_rml23, --phase=ambient rx-only).  Writes both PIDs to
# state files and fails closed if either side cannot come up.
#
#   ./scripts/start_all_rml23.sh [UI_OPTIONS] [-- PRODUCER_OPTIONS]
#
# UI_OPTIONS (all optional; anything before the `--` separator):
#   --ui-sock=<path>            UI data socket (default $UI_SOCK)
#   --stale-ms=<ms>             UI staleness timeout (default 5000)
#   --display-refresh-hz=<hz>   UI render rate (default 30)
#   --no-touch                  disable the touch controller
#
# PRODUCER_OPTIONS (after the `--` separator; all optional).  The recognised flags
# below are dedup'd into ONE effective value each (last-occurrence-wins within the
# user's own args), so the final producer argv carries each flag at most once --
# the binary's later-occurrence-wins is NEVER relied on to resolve a duplicate.
# Unknown flags are passed through verbatim.
#   --phase=<ambient|live-rx>   phase (default ambient)
#   --frames=<n>                frames before self-exit (default 4294967295 ~forever)
#   --rx-gain=<db> --rec-scale=<s> --nco-offset=<hz>
#   --rx-lo=<hz> --rx-bw=<hz> --rf-diag --rf-diag-interval=<n>
#
# PID discipline (M22.1 harness errata, ported): both children are started with the
# shell's own `$!` (direct children, NEVER command substitution), and every cleanup
# re-verifies PID + executable identity before any signal, so a stale or reused PID
# is never killed by mistake.  Only the RML23 binaries are ever signalled -- a
# simultaneously-running 12-class chain is never touched.  UI args and producer
# args are explicitly split at `--` and never forwarded to the wrong side.
#
# State files (under $RML23_LIVE_RUN_DIR, default /tmp/sdr_rml23_live):
#   ui_live_rml23.pid / producer_rml23.pid     PID of each child
#   ui_live_rml23.log / producer_rml23.log     stdout+stderr of each child
#
# Both the UI server (framebuffer map) and the producer (libiio + /dev/mem) need
# root; run as root.  Stop with ./scripts/stop_all_rml23.sh.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/common_rml23.sh"
. "$SCRIPT_DIR/process_guard.sh"

UI_BIN="$(require_bin board_ui_live_rml23)"
PROD_BIN="$(require_bin board_gate9_full_chain_rml23)"
require_libiio_runtime

RUN_DIR="${RML23_LIVE_RUN_DIR:-/tmp/sdr_rml23_live}"
mkdir -p "$RUN_DIR"
UI_PID_FILE="$RUN_DIR/ui_live_rml23.pid"
PROD_PID_FILE="$RUN_DIR/producer_rml23.pid"
UI_LOG="$RUN_DIR/ui_live_rml23.log"
PROD_LOG="$RUN_DIR/producer_rml23.log"

# ---- explicit UI-vs-producer argument split ---------------------------------
# Anything before `--` is a UI option; everything after is passed verbatim to the
# producer.  A UI option we do not recognise is a hard error (never silently
# forwarded to the producer, and never dropped).
UI_SOCK_OPT="$UI_SOCK"
UI_STALE_MS=5000
UI_REFRESH_HZ=30
UI_NO_TOUCH=""
PROD_ARGS=()
_seen_sep=0
for _a in "$@"; do
    if [ "$_a" = "--" ]; then _seen_sep=1; continue; fi
    if [ "$_seen_sep" = "1" ]; then
        PROD_ARGS+=("$_a")
        continue
    fi
    case "$_a" in
        --ui-sock=*) UI_SOCK_OPT="${_a#--ui-sock=}" ;;
        --stale-ms=*) UI_STALE_MS="${_a#--stale-ms=}" ;;
        --display-refresh-hz=*) UI_REFRESH_HZ="${_a#--display-refresh-hz=}" ;;
        --no-touch) UI_NO_TOUCH="--no-touch" ;;
        *) echo "start_all_rml23.sh: unknown UI option '$_a' (producer args go after '--')" >&2
           exit 2 ;;
    esac
done

# ---- effective producer config + dedup (errata 39e5 #11) -------------------
# Every producer flag is parsed EXACTLY ONCE into a single effective value
# (last-occurrence-wins within the user's own args) and REMOVED from the argv, so
# the final argv carries each flag at most once.  We never rely on the binary's
# later-occurrence-wins to silently resolve a duplicate --phase/--frames/
# --rx-gain/--rec-scale.  Unknown producer flags pass through verbatim.  model-sha
# is a FROZEN identity and is always set from $MODEL_RAW_SHA (never from user
# args), so it can never be mis-routed to/from the UI.
PHASE="ambient"
_lr_frames="4294967295"
_lr_rx_lo="-"
_lr_rx_bw="-"
_lr_rx_gain="10"
_lr_rec_scale="1.0"
_lr_nco_offset="0"
_lr_rf_diag=""
_lr_rf_diag_interval="100"
_passthru=()
for _a in "${PROD_ARGS[@]}"; do
    case "$_a" in
        --phase=*) PHASE="${_a#--phase=}" ;;
        --frames=*) _lr_frames="${_a#--frames=}" ;;
        --rx-lo=*) _lr_rx_lo="${_a#--rx-lo=}" ;;
        --rx-bw=*) _lr_rx_bw="${_a#--rx-bw=}" ;;
        --rx-gain=*) _lr_rx_gain="${_a#--rx-gain=}" ;;
        --rec-scale=*) _lr_rec_scale="${_a#--rec-scale=}" ;;
        --nco-offset=*) _lr_nco_offset="${_a#--nco-offset=}" ;;
        --rf-diag) _lr_rf_diag="--rf-diag" ;;
        --rf-diag-interval=*) _lr_rf_diag_interval="${_a#--rf-diag-interval=}" ;;
        *) _passthru+=("$_a") ;;
    esac
done

# ---- refuse to double-start ------------------------------------------------
if [ -f "$UI_PID_FILE" ]; then
    _upid="$(cat "$UI_PID_FILE")"
    if pid_matches_bin "$_upid" "$UI_BIN"; then
        echo "START_ALL_ALREADY_RUNNING ui_pid=$_upid" >&2
        exit 1
    fi
fi
if [ -f "$PROD_PID_FILE" ]; then
    _ppid="$(cat "$PROD_PID_FILE")"
    if pid_matches_bin "$_ppid" "$PROD_BIN"; then
        echo "START_ALL_ALREADY_RUNNING producer_pid=$_ppid" >&2
        exit 1
    fi
fi
rm -f "$UI_PID_FILE" "$PROD_PID_FILE"

UI_PID=""
PROD_PID=""

# Cleanup only the child(ren) we started, and only if the PID still matches the
# RML23 binary.  A PID we never assigned is left untouched.
_cleanup() {
    if [ -n "$PROD_PID" ]; then stop_pid_if_matches "$PROD_PID" "$PROD_BIN" || true; fi
    if [ -n "$UI_PID" ]; then stop_pid_if_matches "$UI_PID" "$UI_BIN" || true; fi
    rm -f "$UI_PID_FILE" "$PROD_PID_FILE"
}

# ---- start the UI server first ---------------------------------------------
# The UI binds the data socket (UI_SOCK), so it must be up before the producer
# starts writing result frames into it.  stdin is /dev/null and stdout+stderr go
# to the LOG FILE only, so neither child ever inherits the control serial console.
nohup "$UI_BIN" \
    --sock="$UI_SOCK_OPT" \
    --ctl-sock="$CTL_SOCK" \
    --stale-ms="$UI_STALE_MS" \
    --display-refresh-hz="$UI_REFRESH_HZ" \
    --model-sha="$MODEL_RAW_SHA" \
    $UI_NO_TOUCH \
    >"$UI_LOG" 2>&1 </dev/null &
UI_PID=$!
echo "$UI_PID" > "$UI_PID_FILE"

_ui_i=0
while [ "$_ui_i" -lt 100 ]; do
    if [ -S "$UI_SOCK_OPT" ] && grep -q 'UI_LIVE_READY' "$UI_LOG" 2>/dev/null; then
        echo "UI_READY sock=$UI_SOCK_OPT pid=$UI_PID"
        break
    fi
    if ! pid_alive "$UI_PID"; then
        echo "START_ALL_FAIL ui_exited (see $UI_LOG)" >&2
        tail -n 20 "$UI_LOG" >&2 || true
        _cleanup
        exit 1
    fi
    _ui_i=$((_ui_i + 1))
    sleep 0.2
done
if [ "$_ui_i" -ge 100 ]; then
    echo "START_ALL_FAIL ui_socket_not_ready (timeout; see $UI_LOG)" >&2
    _cleanup
    exit 1
fi

# ---- start the producer (ambient / live-rx, rx-only) -----------------------
# The producer owns the reverse control socket (CTL_SOCK) and pushes result frames
# to UI_SOCK.  Exactly ONE occurrence of each producer flag: the effective value
# below is the single source of truth (no duplicate --phase/--frames/--rx-gain/
# --rec-scale in the argv).
PROD_ARGV=(
    "--model-json=$MODEL_JSON"
    "--model-raw=$MODEL_RAW"
    "--model-sha=$MODEL_RAW_SHA"
    "--sock=$UI_SOCK_OPT"
    "--ctl-sock=$CTL_SOCK"
    "--phase=$PHASE"
    "--frames=$_lr_frames"
    "--rx-gain=$_lr_rx_gain"
    "--rec-scale=$_lr_rec_scale"
    "--nco-offset=$_lr_nco_offset"
)
[ "$_lr_rx_lo" != "-" ] && PROD_ARGV+=("--rx-lo=$_lr_rx_lo")
[ "$_lr_rx_bw" != "-" ] && PROD_ARGV+=("--rx-bw=$_lr_rx_bw")
[ -n "$_lr_rf_diag" ] && PROD_ARGV+=("$_lr_rf_diag" "--rf-diag-interval=$_lr_rf_diag_interval")
PROD_ARGV+=("${_passthru[@]}")

# One unambiguous effective-config line (board-log observable), with every field
# the contract requires (errata 39e5 #11): phase frames rx_lo rx_bw rx_gain
# nco_offset rec_scale sock ctl_sock.
echo "LIVE_RX_EFFECTIVE_CONFIG phase=$PHASE frames=$_lr_frames rx_lo=$_lr_rx_lo rx_bw=$_lr_rx_bw rx_gain=$_lr_rx_gain nco_offset=$_lr_nco_offset rec_scale=$_lr_rec_scale sock=$UI_SOCK_OPT ctl_sock=$CTL_SOCK"

nohup "$PROD_BIN" "${PROD_ARGV[@]}" >"$PROD_LOG" 2>&1 </dev/null &
PROD_PID=$!
echo "$PROD_PID" > "$PROD_PID_FILE"

# Ready = the control socket is served BY THIS producer PID (never a stale node or
# another process).  If the producer exits (device-not-found / bind failure), fail
# closed and tear the UI down too.
_prod_i=0
while [ "$_prod_i" -lt 100 ]; do
    if socket_served_by "$CTL_SOCK" "$PROD_PID"; then
        echo "PRODUCER_READY ctl_sock=$CTL_SOCK pid=$PROD_PID"
        break
    fi
    if ! pid_alive "$PROD_PID"; then
        echo "START_ALL_FAIL producer_exited (see $PROD_LOG)" >&2
        tail -n 20 "$PROD_LOG" >&2 || true
        _cleanup
        exit 1
    fi
    _prod_i=$((_prod_i + 1))
    sleep 0.2
done
if [ "$_prod_i" -ge 100 ]; then
    echo "START_ALL_FAIL producer_ctl_socket_not_ready (timeout; see $PROD_LOG)" >&2
    _cleanup
    exit 1
fi

echo "START_ALL_READY ui_pid=$UI_PID producer_pid=$PROD_PID sock=$UI_SOCK_OPT ctl_sock=$CTL_SOCK"
exit 0
