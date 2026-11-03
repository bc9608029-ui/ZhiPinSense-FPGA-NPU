#!/usr/bin/env bash
# run_gate7.sh -- Gate 7: load the twelve-class NPU model and verify it against
# the deployment golden set (240 inputs).  NPU only: no SDR, no libiio.
#
# PASS criteria: match_rate >= --min-match-rate (default 0.90) over the golden
# inputs, where match_rate = argmax agreement between the compiled INT8 NPU model
# and the ONNX-Runtime reference (expected_argmax.tsv, golden self-consistency
# 98.3%).  INT8 per-channel symmetric quantization may flip a small number of
# near-boundary argmaxes, hence 0.90, not 1.0.
#
# Requires the NPU device (Device::Open) -- the on-chip iCraft runtime.  Run AFTER
# the bitstream is loaded (same requirement as the npu_only_smoke reference).
#
# Exit code: the binary's own (0/1 = pass / fail).
set -euo pipefail
. "$(dirname "$0")/common.sh"

BIN="$(require_bin board_gate7_12class_npu)"
banner "Gate 7: twelve-class NPU vs deployment golden"

exec "$BIN" \
    --model-json="$MODEL_JSON" \
    --model-raw="$MODEL_RAW" \
    --model-sha="$MODEL_RAW_SHA" \
    --golden="$GOLDEN" \
    --count=240 \
    --min-match-rate=0.90 \
    "$@"
