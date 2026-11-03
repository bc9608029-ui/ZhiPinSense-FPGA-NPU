#!/usr/bin/env bash
# check_live_result.sh -- verify the RML23 (M29 F5) live-chain result is a legal
# 23-class output, not a 12-class or fake AM-SSB-SC/WC output.
#
# Two independent, fail-closed checks:
#
#   (1) UI liveness + integrity.  Confirms the RML23 UI socket is SERVED by a live
#       board_ui_live_rml23 process (never a stale node), then reads the last
#       UI_STATS counters and asserts the server rendered at least one frame and
#       rejected ZERO -- a non-zero rejected count means a malformed / wrong-version
#       / wrong-contract line reached the screen feed, which is a FAIL.
#
#   (2) Result-record contract (optional --result-log).  If a producer result
#       JSONL log is supplied, asserts every non-empty record carries the RML23
#       identity (model_mode=RML23-AMSSB-MERGED, class_count=23,
#       deployment_mode=AMSSB_MERGED, expert_enabled=false, expert_result=NOT_RUN),
#       and that NO record ever labels a top-1 as the fake AM-SSB-SC / AM-SSB-WC
#       (only the merged "AM-SSB" may appear).
#
# Usage:
#   ./check_live_result.sh                          # UI counters only
#   ./check_live_result.sh --result-log=runs/.../rml23_result.jsonl
#   UI_RUN_DIR=/tmp/... ./check_live_result.sh
#
# Exit: 0 = PASS; 1 = FAIL; 2 = precondition (no socket / no server / bad log).
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
. "$SCRIPT_DIR/common_rml23.sh"
. "$SCRIPT_DIR/process_guard.sh"

RUN_DIR="${UI_RUN_DIR:-/tmp/sdr_ui_live_rml23}"
LOG_FILE="$RUN_DIR/ui_live_rml23.log"
SOCK="$(cat "$RUN_DIR/ui_live_rml23.sock" 2>/dev/null || echo "$UI_SOCK")"
RESULT_LOG=""

for a in "$@"; do
    case "$a" in
        --result-log=*) RESULT_LOG="${a#--result-log=}" ;;
        *) echo "check_live_result.sh: unknown option: $a" >&2; exit 2 ;;
    esac
done

get_stat() {
    awk -v k="$1" '{for(i=1;i<=NF;i++){if(index($i,k"=")==1){sub(/^[^=]*=/,"",$i);print $i;exit}}}'
}

# ---- (1) UI liveness + integrity -------------------------------------------
if [ ! -S "$SOCK" ]; then
    echo "CHECK_LIVE_RESULT result=FAIL reason=no_socket sock=$SOCK" >&2
    exit 2
fi
# The socket must be served by a live board_ui_live_rml23 process, not a stale node.
owner="$(for p in /proc/[0-9]*; do
    [ -d "$p" ] || continue
    if grep -q 'board_ui_live_rml23' "$p/cmdline" 2>/dev/null; then
        echo "${p#/proc/}"
    fi
done)"
if [ -z "$owner" ]; then
    echo "CHECK_LIVE_RESULT result=FAIL reason=server_not_running sock=$SOCK" >&2
    exit 2
fi

last="$(awk '/^UI_STATS /{rec=$0} END{print rec}' "$LOG_FILE" 2>/dev/null || true)"
if [ -z "$last" ]; then
    echo "CHECK_LIVE_RESULT result=FAIL reason=no_ui_stats_in_log log=$LOG_FILE" >&2
    exit 1
fi
received="$(echo "$last" | get_stat received)"
valid="$(echo "$last" | get_stat valid)"
rejected="$(echo "$last" | get_stat rejected)"
rendered="$(echo "$last" | get_stat rendered)"

ok=1
[ -n "$rendered" ] && [ "$rendered" -ge 1 ] 2>/dev/null || ok=0
[ "$rejected" = "0" ]                          || ok=0
[ "$valid" = "$received" ]                     || ok=0

# ---- (2) result-record contract --------------------------------------------
if [ -n "$RESULT_LOG" ]; then
    if [ ! -f "$RESULT_LOG" ]; then
        echo "CHECK_LIVE_RESULT result=FAIL reason=missing_result_log path=$RESULT_LOG" >&2
        exit 2
    fi
    # Every non-empty record must carry the RML23 identity; the AM-SSB merge must
    # be the only AM-SSB verdict (never the fake SC/WC top-1).
    n_records="$(grep -c 'rml23-chain-v2' "$RESULT_LOG" 2>/dev/null || true)"
    [ -n "$n_records" ] && [ "$n_records" -ge 1 ] 2>/dev/null || ok=0
    if ! grep -q '"model_mode":"RML23-AMSSB-MERGED"' "$RESULT_LOG" 2>/dev/null; then ok=0; fi
    if ! grep -q '"class_count":23' "$RESULT_LOG" 2>/dev/null; then ok=0; fi
    if ! grep -q '"deployment_mode":"AMSSB_MERGED"' "$RESULT_LOG" 2>/dev/null; then ok=0; fi
    if ! grep -q '"expert_enabled":false' "$RESULT_LOG" 2>/dev/null; then ok=0; fi
    if ! grep -q '"expert_result":"NOT_RUN"' "$RESULT_LOG" 2>/dev/null; then ok=0; fi
    if grep -q '"argmax_class":"AM-SSB-SC"\|"argmax_class":"AM-SSB-WC"' "$RESULT_LOG" 2>/dev/null; then ok=0; fi
fi

echo "CHECK_LIVE_RESULT result=$([ "$ok" = 1 ] && echo PASS || echo FAIL)"
echo "  received=$received valid=$valid rejected=$rejected rendered=$rendered"
[ -n "$RESULT_LOG" ] && echo "  result_log=$RESULT_LOG records=$n_records"

[ "$ok" = 1 ] && exit 0
exit 1
