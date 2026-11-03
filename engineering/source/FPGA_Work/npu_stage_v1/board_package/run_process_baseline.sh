#!/usr/bin/env bash
# CORRECTNESS BASELINE ONLY -- NOT a real-time continuous-inference result.
#
# Board re-test (2026-09-30): a SAME-PROCESS multi-frame run (frames 7-18 in a
# loop, even with a fresh Session + fresh tensors per frame) STILL reports a
# fixed one-frame output delay (class_match=2/12). iCraft 3.39 keeps process-/
# device-level state across forwards, so the previous frame's logits are read
# back. That mode is "same-process continuous: FAIL" and is NOT marked PASS.
#
# The reliable correctness baseline is ONE PROCESS PER FRAME: each frame 7-18 is
# launched as its own short-lived npu_only_smoke process (the shell forks+execs
# a fresh child each iteration; the parent never opens the NPU device, so no
# device handle is inherited by any child). Each child opens its own Device,
# runs one frame, and closes it before exiting. On the board this is 12/12.
#
# This script aggregates the 12 process return codes + MATCH lines and exits 0
# ONLY if all 12 match the PC reference argmax. It is for correctness
# verification; per-process Session setup (~264 ms) is far above real-time
# throughput, so this is not the final continuous-inference path.
#
# This script only runs the compiled model. It does NOT write QSPI, does NOT
# modify SD boot, does NOT update the system, does NOT install packages, does
# NOT download a bitstream, and does NOT auto-retry.
set -u
cd "$(dirname "$0")"

BIN="${NPU_SMOKE_BIN:-./build/npu_only_smoke}"
if [ ! -x "$BIN" ] && [ -x ./npu_only_smoke ]; then BIN=./npu_only_smoke; fi

passed=0
failed=0
matched=0
tmp_dir="$(mktemp -d 2>/dev/null || printf '%s' /tmp/npu_baseline.$$)"
mkdir -p "$tmp_dir"

for f in $(seq 7 18); do
    out="$tmp_dir/frame$f.log"
    "$BIN" --model model.json --raw model.raw \
           --tensor expected_tensor_plddr.bin \
           --frame "$f" --reference reference_argmax.txt > "$out" 2>&1
    rc=$?
    if [ "$rc" -ne 0 ]; then
        failed=$((failed+1))
        echo "frame $f: PROCESS FAIL (rc=$rc)"
        cat "$out"
        continue
    fi
    if grep -q 'V2_NPU_ONLY_SMOKE_REFERENCE_MATCH' "$out"; then
        passed=$((passed+1)); matched=$((matched+1))
        echo "frame $f: PASS"
    else
        failed=$((failed+1))
        echo "frame $f: MISMATCH"
        cat "$out"
    fi
done

echo
echo "baseline: passed=$passed failed=$failed  class_match=$matched/12"
rm -rf "$tmp_dir"

if [ "$passed" -eq 12 ] && [ "$failed" -eq 0 ]; then
    echo "BASELINE_RESULT=PASS (12/12, one process per frame)"
    exit 0
else
    echo "BASELINE_RESULT=FAIL"
    exit 1
fi
