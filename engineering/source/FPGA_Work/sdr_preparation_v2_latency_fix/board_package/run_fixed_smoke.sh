#!/usr/bin/env bash
# Fixed build: SMOKE (1 joint cycle) with per-phase timing.
#
# Resource-reuse build (input Tensors allocated once, input_allocations==2).
# Step 2 of the on-board retest order: after baseline_diag has reproduced the
# spike, run this smoke before the longer fixed runs.
#
# Emits CORRECTNESS_RESULT / LATENCY_RESULT / RESOURCE_RESULT / FINAL_RESULT
# (PASS|FAIL each) plus LATENCY_PHASE_*/LATENCY_SUMMARY.  The program enforces
# all three gates itself and exits 0 ONLY when correctness AND latency
# (gt_100ms==0, p99<=5ms, max<=10ms, gt_10ms==0 on total_inference) AND
# resource (input_allocations==2, completed_cycles==opt.cycles,
# frame_timings.size()==opt.cycles*npu_frames_per_cycle) all PASS.  This script
# exec's the binary, so that exit code is passed through unchanged.
set -euo pipefail
cd "$(dirname "$0")"

BIN="${FIXED_BIN:-./build/continuous_joint_stress_fixed}"
if [ ! -x "$BIN" ] && [ -x ./continuous_joint_stress_fixed ]; then BIN=./continuous_joint_stress_fixed; fi

exec "$BIN" \
    --model model.json \
    --raw model.raw \
    --iq iq_input.bin \
    --expected-tensor expected_tensor_plddr.bin \
    --reference reference_argmax.txt \
    --reg-base 0x400C0000 \
    --first 7 --last 18 \
    --cycles 1
