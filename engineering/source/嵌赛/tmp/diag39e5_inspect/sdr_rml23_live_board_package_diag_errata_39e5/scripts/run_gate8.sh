#!/usr/bin/env bash
# run_gate8.sh -- Gate 8: results -> UI JSONL (no SDR, no NPU).
#
# Replays deployment_golden/expected_logits.tsv through chain::fill_result() and
# ui::result_frame_v2_line(), emitting one §八 JSONL record per frame to stdout
# (and optionally a Unix socket via --sock).  Every emitted line is validated
# (well-formed JSON, argmax/class self-consistency, probabilities sum ~1,
# class_count==12, version tag, model_sha).
#
# PASS criteria: emitted == count, valid == emitted.
#
# Exit code: the binary's own (0/1 = pass / fail).
set -euo pipefail
. "$(dirname "$0")/common.sh"

BIN="$(require_bin board_gate8_ui)"
banner "Gate 8: ResultFrame -> UI JSONL"

exec "$BIN" \
    --logits-tsv="$GOLDEN/expected_logits.tsv" \
    --model-sha="$MODEL_RAW_SHA" \
    --count=240 \
    "$@"
