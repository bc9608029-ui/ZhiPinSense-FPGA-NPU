#!/usr/bin/env bash
# Re-arm sweep: run the 7..18 sequence test once per completion re-arm mechanism
# to identify the exact official API that reaches a persistent-Device PASS.
#
#   none          -> single persistent Session, no re-arm (reproduces the stale bug)
#   setready      -> Tensor::setReady(false) before waitForReady (software re-arm)
#   reset1        -> Device::reset(1) before each frame ("reset FPGA state only")
#   reset1_apply  -> Device::reset(1) + Session::apply() before each frame
#   reopen        -> per-frame Device Close/Open (known 12/12 correctness control)
#
# Each experiment changes exactly ONE variable.  Device is opened once per
# invocation (reopen opens/closes once per frame by design).  No private FPGA
# register, no setOpWait/getOpWait, no fake sleep, no frame drop/shift/warm-up.
#
# Exits 0 iff the 'reopen' control passes (harness sanity).  The winning
# persistent re-arm is whichever non-reopen mechanism ALSO prints RT_RESULT=PASS.
set -euo pipefail
cd "$(dirname "$0")"

BIN="${REALTIME_BIN:-./build/npu_realtime}"
if [ ! -x "$BIN" ] && [ -x ./npu_realtime ]; then BIN=./npu_realtime; fi

for REARM in none setready reset1 reset1_apply reopen; do
  echo "===== rearm=$REARM ====="
  "$BIN" \
    --model model.json \
    --raw model.raw \
    --tensor tensor_19frames_sint8.bin \
    --reference reference_argmax.txt \
    --rearm "$REARM" \
    --test sequence \
    --frames 12 \
    --rounds 1
  echo ""
done

echo "===== sweep summary ====="
echo "Look for a persistent rearm (none/setready/reset1/reset1_apply) that prints"
echo "RT_RESULT=PASS. 'reopen' is the correctness control and should always PASS."
