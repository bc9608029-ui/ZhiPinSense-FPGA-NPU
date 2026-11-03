#!/usr/bin/env bash
# Continuous joint stress: SMOKE (1 joint cycle).
#
# One cycle = 19 FPGA frames (fixed IQ loop -> PL DDR -> Mandatory Core ->
# tensor readback + per-cycle Golden compare) + NPU inference on frames 7..18
# with Device::reset(1) re-arm, all on ONE persistent Device/Session.
#
# Emits STRESS_RESULT=PASS/FAIL.  Exits 0 on PASS, 1 on FAIL.
set -euo pipefail
cd "$(dirname "$0")"

BIN="${STRESS_BIN:-./build/continuous_joint_stress}"
if [ ! -x "$BIN" ] && [ -x ./continuous_joint_stress ]; then BIN=./continuous_joint_stress; fi

exec "$BIN" \
    --model model.json \
    --raw model.raw \
    --iq iq_input.bin \
    --expected-tensor expected_tensor_plddr.bin \
    --reference reference_argmax.txt \
    --reg-base 0x400C0000 \
    --first 7 --last 18 \
    --cycles 1
