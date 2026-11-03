#!/usr/bin/env bash
# run_gate8_ui_socket_test.sh -- Gate 8 -> socket -> UI server round-trip test.
#
# Requires the LIVE UI server to already be running (socket node + UI_LIVE_READY
# in its log).  Runs Gate 8 (golden logits -> result_frame_v2 JSONL) with
# --sock=<sock> --count=<N>, then asserts the server's coalescing counters against
# the §四 contract:
#
#   received == N,  valid == N,  rejected == 0,
#   rendered >= 1 && rendered <= valid,
#   coalesced == valid - rendered,
#   last_frame_id == N   (the last frame_id the producer sent)
#
# Exit 0 = PASS, 1 = assertion failure, 2 = precondition (no socket / no binary).
# The whole thing is OFFLINE_REPLAY (golden data, no NPU, no SDR) -- it is NEVER
# a LIVE chain.
set -euo pipefail
. "$(dirname "$0")/common.sh"

BIN="$(require_bin board_gate8_ui)"
RUN_DIR="/tmp/sdr_ui_live"
LOG_FILE="$RUN_DIR/ui_live.log"
SOCK="$(cat "$RUN_DIR/ui_live.sock" 2>/dev/null || echo /run/sdr_amr_ui.sock)"
COUNT="${COUNT:-240}"

if [ ! -S "$SOCK" ]; then
    echo "GATE8_UI_SOCKET_TEST result=FAIL reason=socket_not_ready sock=$SOCK" >&2
    exit 2
fi

banner "Gate 8 -> socket -> UI server (OFFLINE_REPLAY)"

# Extract one key=value field from a UI_STATS line on stdin.
get_stat() {
    awk -v k="$1" '{for(i=1;i<=NF;i++){if(index($i,k"=")==1){sub(/^[^=]*=/,"",$i);print $i;exit}}}'
}

# Send N golden frames into the socket; the gate's own verdict is also checked.
"$BIN" \
    --logits-tsv="$GOLDEN/expected_logits.tsv" \
    --model-sha="$MODEL_RAW_SHA" \
    --count="$COUNT" \
    --sock="$SOCK"
GATE8_RC=$?
if [ "$GATE8_RC" -ne 0 ]; then
    echo "GATE8_UI_SOCKET_TEST result=FAIL reason=gate8_exit_code=$GATE8_RC" >&2
    exit 1
fi

# Poll the server log until it has drained COUNT frames (UI_STATS printed ~1 Hz).
last=""
i=0
while [ "$i" -lt 60 ]; do
    last="$(awk '/^UI_STATS /{rec=$0} END{print rec}' "$LOG_FILE" 2>/dev/null || true)"
    rcv="$(echo "$last" | get_stat received)"
    if [ -n "$rcv" ] && [ "$rcv" -ge "$COUNT" ] 2>/dev/null; then break; fi
    i=$((i + 1))
    sleep 0.2
done

if [ -z "$last" ]; then
    echo "GATE8_UI_SOCKET_TEST result=FAIL reason=no_ui_stats_in_log" >&2
    exit 1
fi

received="$(echo "$last" | get_stat received)"
valid="$(echo "$last" | get_stat valid)"
rejected="$(echo "$last" | get_stat rejected)"
rendered="$(echo "$last" | get_stat rendered)"
coalesced="$(echo "$last" | get_stat coalesced)"
last_frame_id="$(echo "$last" | get_stat last_frame_id)"

ok=1
[ "$received" = "$COUNT" ]                    || ok=0
[ "$valid" = "$COUNT" ]                       || ok=0
[ "$rejected" = "0" ]                         || ok=0
[ "$rendered" -ge 1 ] 2>/dev/null             || ok=0
[ "$rendered" -le "$valid" ] 2>/dev/null      || ok=0
[ "$coalesced" = "$((valid - rendered))" ]    || ok=0
[ "$last_frame_id" = "$COUNT" ]               || ok=0

echo "GATE8_UI_SOCKET_TEST result=$([ "$ok" = 1 ] && echo PASS || echo FAIL)"
echo "  received=$received valid=$valid rejected=$rejected rendered=$rendered coalesced=$coalesced last_frame_id=$last_frame_id"

[ "$ok" = 1 ] && exit 0
exit 1
