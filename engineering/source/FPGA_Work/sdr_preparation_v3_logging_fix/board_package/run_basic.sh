#!/usr/bin/env bash
# Continuous joint stress (v1 program): BASIC (10 joint cycles) — non-intrusive.
#
# Ten cycles back-to-back on ONE persistent Device/Session; each cycle runs the
# full FPGA PL-DDR + Mandatory Core data path (19 frames, per-cycle Golden
# compare) followed by NPU inference on frames 7..18 with Device::reset(1)
# re-arm.
#
# Live per-frame output to the 115200 serial console fabricates latency spikes
# (observer effect), so the whole run is redirected to a timestamped log file
# and the console stays quiet during the run.  A short summary is printed only
# after the program exits; the real exit code is preserved.
#
# Emits STRESS_RESULT=PASS/FAIL.  Exits 0 on PASS, 1 on FAIL.
set -euo pipefail
cd "$(dirname "$0")"

BIN="${STRESS_BIN:-./build/continuous_joint_stress}"
if [ ! -x "$BIN" ] && [ -x ./continuous_joint_stress ]; then BIN=./continuous_joint_stress; fi

LOG_DIR="${LOG_DIR:-./logs}"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/basic_$(date +%Y%m%d_%H%M%S).log"

set +e
"$BIN" \
    --model model.json \
    --raw model.raw \
    --iq iq_input.bin \
    --expected-tensor expected_tensor_plddr.bin \
    --reference reference_argmax.txt \
    --reg-base 0x400C0000 \
    --first 7 --last 18 \
    --cycles 10 > "$LOG_FILE" 2>&1
rc=$?
set -e

grep -E 'STRESS_SUMMARY|STRESS_RESULT' "$LOG_FILE" || true
echo "LOG_FILE=$LOG_FILE"
echo "EXIT_CODE=$rc"
exit "$rc"
