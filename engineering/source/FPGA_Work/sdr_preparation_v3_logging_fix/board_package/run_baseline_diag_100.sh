#!/usr/bin/env bash
# Baseline diagnostic: 100 joint cycles with per-phase timing (non-intrusive).
#
# ROOT CAUSE (confirmed on hardware): live per-frame output to the 115200 serial
# console backpressures the UART and perturbs scheduling, fabricating 425~978 ms
# false spikes.  So this script redirects the WHOLE run to a timestamped log
# file and keeps the serial console quiet during the run; a short summary is
# printed only after the program exits, and the real exit code is preserved.
#
# The baseline keeps per-frame input Tensor allocation (input_allocations==2400)
# as the control: under non-intrusive logging it still shows p99<1ms, proving
# input allocation is NOT the spike cause.
#
# Verdict lines (program-enforced): BASELINE_CORRECTNESS_RESULT,
# BASELINE_LATENCY_RESULT, BASELINE_FINAL_RESULT.  BASELINE_SPIKE_REPRODUCED is
# DIAGNOSTIC ONLY and does not decide the exit code.
set -euo pipefail
cd "$(dirname "$0")"

BIN="${BASELINE_DIAG_BIN:-./build/continuous_joint_stress_baseline_diag}"
if [ ! -x "$BIN" ] && [ -x ./continuous_joint_stress_baseline_diag ]; then BIN=./continuous_joint_stress_baseline_diag; fi

LOG_DIR="${LOG_DIR:-./logs}"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/baseline_diag_100_$(date +%Y%m%d_%H%M%S).log"

set +e
"$BIN" \
    --model model.json \
    --raw model.raw \
    --iq iq_input.bin \
    --expected-tensor expected_tensor_plddr.bin \
    --reference reference_argmax.txt \
    --reg-base 0x400C0000 \
    --first 7 --last 18 \
    --cycles 100 > "$LOG_FILE" 2>&1
rc=$?
set -e

grep -E 'LATENCY_PHASE total_inference|STRESS_SUMMARY|LATENCY_SUMMARY|BASELINE_SPIKE_REPRODUCED|BASELINE_CORRECTNESS_RESULT|BASELINE_LATENCY_RESULT|BASELINE_FINAL_RESULT' "$LOG_FILE" || true
echo "LOG_FILE=$LOG_FILE"
echo "EXIT_CODE=$rc"
exit "$rc"
