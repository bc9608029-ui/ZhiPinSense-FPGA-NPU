#!/usr/bin/env bash
# Host-side behavior test for the non-intrusive run scripts (no iCraft, no
# board).  It verifies, with a mock binary:
#   1. every run script passes `bash -n`;
#   2. the real exit code of the binary is passed through unchanged;
#   3. per-frame output goes ONLY to the timestamped log file (serial stays
#      quiet during the run), and a summary is printed only after exit.
#
# Run from WSL:  bash /mnt/f/FPGA_Work/sdr_preparation_v3_logging_fix/host_tests/test_script_behavior.sh
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG="$HERE/../board_package"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
LOG_DIR="$TMP/logs"

fail=0

# ---- 1. bash -n syntax check on all 8 run scripts ----
for s in run_baseline_diag_100.sh run_fixed_smoke.sh run_fixed_basic.sh \
         run_fixed_stress_100.sh run_fixed_stress_1000.sh \
         run_smoke.sh run_basic.sh run_stress.sh; do
    if bash -n "$PKG/$s" 2>"$TMP/syn.err"; then
        echo "syntax OK: $s"
    else
        echo "SYNTAX FAIL: $s"; cat "$TMP/syn.err"; fail=1
    fi
done

# ---- mock binary: per-frame line + summary/verdict lines + controllable rc ----
cat > "$TMP/mock" <<'EOF'
#!/bin/sh
echo "STRESS_NPU cycle=0 frame=7 pred=1 ref=1 result=MATCH forward=0.7"
echo "LATENCY_PHASE total_inference count=1200 p50=0.700 p95=0.800 p99=0.750 max=1.100 gt_5ms=0 gt_10ms=0 gt_100ms=0"
echo "STRESS_SUMMARY cycles=100 npu_frames=1200 match=1200/1200 delay_shift=0/1199 timeout=0 error=0 fpga_mismatch_cycles=0 version_fail=0"
echo "LATENCY_SUMMARY rss_start_kb=1000 rss_end_kb=1000 input_allocations=2 output_host_conversions=1200 frames_recorded=1200"
echo "BASELINE_SPIKE_REPRODUCED=NO"
echo "BASELINE_CORRECTNESS_RESULT=PASS"
echo "BASELINE_LATENCY_RESULT=PASS"
echo "BASELINE_FINAL_RESULT=PASS"
echo "CORRECTNESS_RESULT=PASS"
echo "LATENCY_RESULT=PASS"
echo "RESOURCE_RESULT=PASS"
echo "FINAL_RESULT=PASS"
echo "STRESS_RESULT=PASS"
exit "${MOCK_RC:-0}"
EOF
chmod +x "$TMP/mock"

# ---- 2. fixed script: exit-code pass-through (0 and 3) + log-only behavior ----
set +e
out=$(MOCK_RC=0 FIXED_BIN="$TMP/mock" LOG_DIR="$LOG_DIR" "$PKG/run_fixed_stress_100.sh" 2>&1)
rc=$?
set -e
if [ "$rc" -ne 0 ]; then echo "FAIL: fixed rc=0 pass-through (got $rc)"; fail=1; fi
echo "$out" | grep -q 'EXIT_CODE=0' || { echo "FAIL: fixed EXIT_CODE=0 line missing"; fail=1; }
echo "$out" | grep -q 'FINAL_RESULT=PASS' || { echo "FAIL: fixed summary missing FINAL_RESULT"; fail=1; }
# Per-frame line must be in the log, NOT on stdout (serial stays quiet during run).
if echo "$out" | grep -q 'STRESS_NPU'; then echo "FAIL: per-frame line leaked to stdout"; fail=1; fi
logfile=$(echo "$out" | sed -n 's/^LOG_FILE=//p')
if [ -z "$logfile" ] || [ ! -s "$logfile" ]; then echo "FAIL: log file missing/empty"; fail=1; fi
grep -q 'STRESS_NPU' "$logfile" || { echo "FAIL: per-frame output not in log"; fail=1; }

set +e
out3=$(MOCK_RC=3 FIXED_BIN="$TMP/mock" LOG_DIR="$LOG_DIR" "$PKG/run_fixed_stress_100.sh" 2>&1)
rc3=$?
set -e
if [ "$rc3" -ne 3 ]; then echo "FAIL: fixed rc=3 pass-through (got $rc3)"; fail=1; fi
echo "$out3" | grep -q 'EXIT_CODE=3' || { echo "FAIL: fixed EXIT_CODE=3 line missing"; fail=1; }

# ---- 3. baseline script: exit-code pass-through + BASELINE_FINAL_RESULT summary ----
set +e
outb=$(MOCK_RC=0 BASELINE_DIAG_BIN="$TMP/mock" LOG_DIR="$LOG_DIR" "$PKG/run_baseline_diag_100.sh" 2>&1)
rcb=$?
set -e
if [ "$rcb" -ne 0 ]; then echo "FAIL: baseline rc=0 pass-through (got $rcb)"; fail=1; fi
echo "$outb" | grep -q 'BASELINE_FINAL_RESULT=PASS' || { echo "FAIL: baseline summary missing BASELINE_FINAL_RESULT"; fail=1; }
echo "$outb" | grep -q 'BASELINE_SPIKE_REPRODUCED=NO' || { echo "FAIL: baseline summary missing BASELINE_SPIKE_REPRODUCED"; fail=1; }

# ---- 4. v1 stress script: exit-code pass-through + STRESS_RESULT summary ----
set +e
outv=$(MOCK_RC=0 STRESS_BIN="$TMP/mock" LOG_DIR="$LOG_DIR" "$PKG/run_stress.sh" 2>&1)
rcv=$?
set -e
if [ "$rcv" -ne 0 ]; then echo "FAIL: v1 stress rc=0 pass-through (got $rcv)"; fail=1; fi
echo "$outv" | grep -q 'STRESS_RESULT=PASS' || { echo "FAIL: v1 stress summary missing STRESS_RESULT"; fail=1; }

if [ "$fail" -eq 0 ]; then
    echo "ALL SCRIPT TESTS PASSED"
    exit 0
fi
echo "SCRIPT TESTS FAILED"
exit 1
