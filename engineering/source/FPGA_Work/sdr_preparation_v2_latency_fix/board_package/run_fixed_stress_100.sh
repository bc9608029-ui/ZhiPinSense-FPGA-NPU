#!/usr/bin/env bash
# Fixed build: STRESS (100 joint cycles) with per-phase timing.
#
# Resource-reuse build (input Tensors allocated once, input_allocations==2).
# Step 4 of the on-board retest order.  The hard latency gate for a fix is
# evaluated on the LATENCY_PHASE lines: gt_100ms==0, p99<=5ms, max<=10ms,
# gt_10ms==0 on total_inference (and no spike in any phase).  If these are not
# met, the result is NO_GO — do not relax the gate.
#
# Emits CORRECTNESS_RESULT / LATENCY_RESULT / RESOURCE_RESULT / FINAL_RESULT
# (PASS|FAIL each) plus LATENCY_PHASE_*/LATENCY_SUMMARY.  The program enforces
# the hard latency gate itself on total_inference (gt_100ms==0, p99<=5ms,
# max<=10ms, gt_10ms==0) plus the correctness and resource gates, and exits 0
# ONLY when all three PASS — no manual log reading needed.  This script exec's
# the binary, so that exit code is passed through unchanged.
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
    --cycles 100
