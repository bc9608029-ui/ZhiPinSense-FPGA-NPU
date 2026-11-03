#!/usr/bin/env bash
# Baseline diagnostic: 100 joint cycles with per-phase timing.
#
# MUST reproduce the original periodic latency spike (from cycle ~58, every 6
# cycles at frame=7, forward ~425/604/937 ms).  If it does NOT reproduce the
# spike, STOP — do not proceed to the fixed build and do not claim a fix.
#
# Emits STRESS_RESULT=PASS/FAIL (correctness), per-frame LATENCY_FRAME,
# per-phase LATENCY_PHASE_* (reset/dequantize/input_prepare/forward_submit/
# wait_ready/output_to_host/output_read/forward_legacy/total_inference, each
# with count/p50/p95/p99/max/gt_5ms/gt_10ms/gt_100ms) and LATENCY_SUMMARY (RSS
# + resource counters).  Then emits BASELINE_SPIKE_FRAME (one line per slow
# frame) and BASELINE_SPIKE_REPRODUCED=YES|NO.
#
# The program enforces the reproduction gate: it exits 0 ONLY when the spike is
# reproduced (>=1 frame with forward_legacy > 100 ms) AND correctness passes.
# On BASELINE_SPIKE_REPRODUCED=NO it exits non-zero and forbids running the
# fixed tests.  This script exec's the binary, so that exit code is passed
# through unchanged.
set -euo pipefail
cd "$(dirname "$0")"

BIN="${BASELINE_DIAG_BIN:-./build/continuous_joint_stress_baseline_diag}"
if [ ! -x "$BIN" ] && [ -x ./continuous_joint_stress_baseline_diag ]; then BIN=./continuous_joint_stress_baseline_diag; fi

exec "$BIN" \
    --model model.json \
    --raw model.raw \
    --iq iq_input.bin \
    --expected-tensor expected_tensor_plddr.bin \
    --reference reference_argmax.txt \
    --reg-base 0x400C0000 \
    --first 7 --last 18 \
    --cycles 100
