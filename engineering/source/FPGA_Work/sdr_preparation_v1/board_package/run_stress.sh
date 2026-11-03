#!/usr/bin/env bash
# Continuous joint stress: STRESS (100 joint cycles).
#
# 100 cycles back-to-back on ONE persistent Device/Session = 1,945,600 IQ
# samples + 1,945,600 tensor samples through the FPGA, 100 FPGA tasks, and
# 1200 NPU inferences (frames 7..18, Device::reset(1) re-arm).  Per-cycle the
# FPGA tensor is byte-compared against the frozen Golden capture; every NPU
# frame is argmax-compared against reference_argmax.txt.  Emits
# STRESS_RESULT=PASS/FAIL.  Exits 0 on PASS, 1 on FAIL.
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
    --cycles 100
