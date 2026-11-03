#!/usr/bin/env bash
# FPGA -> NPU joint correctness closed-loop run.
#
# Phase A: frozen IQ -> PL DDR -> FPGA Mandatory Core -> tensor -> byte-compare
#          vs expected_tensor_plddr.bin (mismatch != 0 => STOP, NPU skipped).
# Phase B: frames 7..18, per-frame NPU (exp4 Device reopen lifecycle), argmax
#          vs reference_argmax.txt.
#
# Emits JOINT_CORRECTNESS_PASS/FAIL and REALTIME_NOT_YET_VALIDATED.  Phase B uses
# the exp4 per-frame Device-reopen lifecycle, which has been board-run three
# times (12/12 MATCH, no one-frame delay).  It is correctness-verified but NOT
# real-time (per-frame Device/Session setup overhead), so REALTIME_NOT_YET_VALIDATED
# is always printed.
#
# This script does NOT write QSPI, does NOT modify SD boot, does NOT update the
# system, does NOT install packages, does NOT download a bitstream, and does NOT
# auto-retry.  It only runs the compiled joint smoke program against the already
# loaded bitstream.
set -euo pipefail
cd "$(dirname "$0")"

BIN="${JOINT_SMOKE_BIN:-./build/fpga_npu_joint_smoke}"
if [ ! -x "$BIN" ] && [ -x ./fpga_npu_joint_smoke ]; then BIN=./fpga_npu_joint_smoke; fi

exec "$BIN" \
    --model model.json \
    --raw model.raw \
    --iq iq_input.bin \
    --expected-tensor expected_tensor_plddr.bin \
    --reference reference_argmax.txt \
    --reg-base 0x400C0000 \
    --frames 7 18
