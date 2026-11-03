#!/usr/bin/env bash
# Fixed build: BASIC (10 joint cycles) — non-intrusive logging.
#
# Resource-reuse build (input_allocations==2).  Whole run goes to a timestamped
# log file; the serial console stays quiet during the run (see the observer-
# effect root cause in run_baseline_diag_100.sh).  A short summary is printed
# only after the program exits; the real exit code is preserved.
#
# Verdict lines (program-enforced): CORRECTNESS_RESULT, LATENCY_RESULT,
# RESOURCE_RESULT, FINAL_RESULT.
set -euo pipefail
cd "$(dirname "$0")"

BIN="${FIXED_BIN:-./build/continuous_joint_stress_fixed}"
if [ ! -x "$BIN" ] && [ -x ./continuous_joint_stress_fixed ]; then BIN=./continuous_joint_stress_fixed; fi

LOG_DIR="${LOG_DIR:-./logs}"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/fixed_basic_$(date +%Y%m%d_%H%M%S).log"

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

grep -E 'LATENCY_PHASE total_inference|STRESS_SUMMARY|LATENCY_SUMMARY|CORRECTNESS_RESULT|LATENCY_RESULT|RESOURCE_RESULT|FINAL_RESULT' "$LOG_FILE" || true
echo "LOG_FILE=$LOG_FILE"
echo "EXIT_CODE=$rc"
exit "$rc"
