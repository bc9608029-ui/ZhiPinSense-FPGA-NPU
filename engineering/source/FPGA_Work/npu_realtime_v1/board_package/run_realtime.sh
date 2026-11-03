#!/usr/bin/env bash
# Persistent-Device continuous-inference PASS test.
#
# Runs, with the chosen completion re-arm (REARM env, default 'reset1'):
#   1. three rounds of a 100-frame sequence test (frames 7..18 cycled, argmax vs
#      reference, no delay / no timeout / no error);
#   2. one alternating test (frames 7 vs 10) that compares FULL logits to a
#      known-good reopen baseline, proving the output truly updates.
#
# PASS conditions (all must hold):
#   * Device opened once per invocation, closed once (the program does this);
#   * >=100 consecutive frames, every frame correct, no one-frame delay;
#   * no dropped/duplicate/stale/reordered frame;
#   * timeout=0, error=0;
#   * frames 7..18 repeated, all match reference;
#   * alternating full-logits test shows no stale output;
#   * per-frame setup is ~ms (no ~265 ms Device reopen in the persistent path).
#
# The script exits 0 only if EVERY invocation prints RT_RESULT=PASS.
set -uo pipefail
cd "$(dirname "$0")"

REARM="${REARM:-reset1}"
FRAMES="${FRAMES:-100}"
ROUNDS="${ROUNDS:-3}"
ALT_ITER="${ALT_ITER:-24}"

BIN="${REALTIME_BIN:-./build/npu_realtime}"
if [ ! -x "$BIN" ] && [ -x ./npu_realtime ]; then BIN=./npu_realtime; fi

run() {
  "$BIN" \
    --model model.json \
    --raw model.raw \
    --tensor tensor_19frames_sint8.bin \
    --reference reference_argmax.txt \
    --rearm "$REARM" \
    "$@"
}

overall=0

echo "===== continuous sequence: $FRAMES frames x $ROUNDS rounds (rearm=$REARM) ====="
for r in $(seq 1 "$ROUNDS"); do
  echo "----- round $r -----"
  if ! run --test sequence --frames "$FRAMES" --rounds "$r" | tee /dev/stderr | grep -q '^RT_RESULT=PASS'; then
    overall=1
  fi
done

echo ""
echo "===== alternating full-logits test (frames 7 vs 10, rearm=$REARM) ====="
if ! run --test alternating --alt-iterations "$ALT_ITER" | tee /dev/stderr | grep -q '^RT_RESULT=PASS'; then
  overall=1
fi

echo ""
if [ "$overall" -eq 0 ]; then
  echo "REALTIME_CONTINUOUS_PASS"
  exit 0
else
  echo "REALTIME_CONTINUOUS_FAIL"
  exit 1
fi
