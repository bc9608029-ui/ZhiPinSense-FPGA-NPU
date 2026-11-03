#!/usr/bin/env bash
set -euo pipefail
ROOT=/root/rml24_scan_execution_20261027
mkdir "$ROOT/historical_replay_inputs"
tar -xzf /root/rml24_stage7_execution_20261027/waterfall_fix1_final_captures.tar.gz -C "$ROOT/historical_replay_inputs" --strip-components=2 --wildcards 'rml24_stage7_waterfall_fix1_r1_20261027/capture/*.candidate.inputs.bin'
/root/amr_rescue_20261025/build/npu_stream /root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.json /root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16/rml24_adamrv11_bf16.raw "$ROOT/replay_npu.sock" > "$ROOT/historical_replay_npu.log" 2>&1 &
PID=$!
trap 'kill "$PID" 2>/dev/null || true; wait "$PID" 2>/dev/null || true' EXIT
for i in $(seq 1 100); do [ -S "$ROOT/replay_npu.sock" ] && break; sleep .1; done
OPENBLAS_NUM_THREADS=1 python3 "$ROOT/historical_npu_replay.py"
wait "$PID"
trap - EXIT
echo HISTORICAL_REPLAY_RUN_PASS