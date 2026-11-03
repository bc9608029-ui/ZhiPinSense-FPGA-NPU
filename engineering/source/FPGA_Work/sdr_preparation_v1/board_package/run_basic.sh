#!/usr/bin/env bash
# Continuous joint stress: BASIC (10 joint cycles).
#
# Ten cycles back-to-back on ONE persistent Device/Session; each cycle runs the
# full FPGA PL-DDR + Mandatory Core data path (19 frames, per-cycle Golden
# compare) followed by NPU inference on frames 7..18 with Device::reset(1)
# re-arm.  Emits STRESS_RESULT=PASS/FAIL.  Exits 0 on PASS, 1 on FAIL.
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
    --cycles 10
