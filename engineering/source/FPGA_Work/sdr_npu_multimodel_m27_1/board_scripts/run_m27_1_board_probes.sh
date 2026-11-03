#!/usr/bin/env bash
# M27.1 board one-click multi-model probe driver.
# Run ON the FMQL30TAI Linux image.  Fail-closed: any SHA mismatch, missing model,
# or baseline probe failure aborts before declaring any conclusion.
#
# Model paths come from env (defaults point at the frozen production files):
#   MODEL_A_JSON / MODEL_A_RAW  (12-class, frozen)
#   MODEL_B_JSON / MODEL_B_RAW  (8-class board-proven model)
# Optional:   WARMUP  FRAMES  ROUNDS  SKIP_BUILD=1
set -euo pipefail

HERE="$(cd "$(dirname "$0")/.." && pwd)"
PROBES="$HERE/probes"
RESULTS="$HERE/results"
mkdir -p "$RESULTS"

# ---- frozen model identities (see docs/M27_1_MODEL_SELECTION.md) ----
A_JSON_SHA="51364bdf49d280944094f7af89ea4c759b3ae4d0d350be5f8c43e0c5849ab834"
A_RAW_SHA="2ae95275fe362bdc463e1ded5dfc974b5d77eaae5ce2d2184beebdb5dad7ec2c"
B_JSON_SHA="ad57fc0b4a9ec5ae6e8cd2d2c2c0c91f81ef4e5fc7898447b322dc00c349a2e4"
B_RAW_SHA="c48979b3ab1bc62fa2efcfb07202ee640513f424244d15d089c89a6d2260b42a"

MODEL_A_JSON="${MODEL_A_JSON:-/opt/sdr/model_12class/model_12class.json}"
MODEL_A_RAW="${MODEL_A_RAW:-/opt/sdr/model_12class/model_12class.raw}"
MODEL_B_JSON="${MODEL_B_JSON:-/opt/sdr/model_8class/model.json}"
MODEL_B_RAW="${MODEL_B_RAW:-/opt/sdr/model_8class/model.raw}"

WARMUP="${WARMUP:-100}"
FRAMES="${FRAMES:-1000}"
ROUNDS="${ROUNDS:-2}"

# ---- fail-closed model identity check BEFORE any probe runs ----
for f in "$MODEL_A_JSON" "$MODEL_A_RAW" "$MODEL_B_JSON" "$MODEL_B_RAW"; do
  [ -f "$f" ] || { echo "ABORT: model file missing: $f"; exit 1; }
done

actual_a_json=$(sha256sum "$MODEL_A_JSON" | awk '{print $1}')
actual_a_raw=$(sha256sum "$MODEL_A_RAW"  | awk '{print $1}')
actual_b_json=$(sha256sum "$MODEL_B_JSON" | awk '{print $1}')
actual_b_raw=$(sha256sum "$MODEL_B_RAW"  | awk '{print $1}')

[ "$actual_a_json" = "$A_JSON_SHA" ] || { echo "ABORT: MODEL_A_JSON SHA mismatch (refusing to run on a non-frozen model)"; exit 1; }
[ "$actual_a_raw"  = "$A_RAW_SHA"  ] || { echo "ABORT: MODEL_A_RAW SHA mismatch (refusing to run on a non-frozen model)"; exit 1; }
[ "$actual_b_json" = "$B_JSON_SHA" ] || { echo "ABORT: MODEL_B_JSON SHA mismatch (overriding model B? update the frozen SHA or pass the legal model)"; exit 1; }
[ "$actual_b_raw"  = "$B_RAW_SHA"  ] || { echo "ABORT: MODEL_B_RAW SHA mismatch"; exit 1; }
echo "model identity verified (A/B frozen SHAs match)"

# ---- build (unless SKIP_BUILD=1) ----
if [ "${SKIP_BUILD:-0}" != "1" ]; then
  ( cd "$PROBES" && ./build_on_board.sh )
fi
BIN="$PROBES/build"

run_probe() {  # name -> writes RESULTS/<name>.json, echoes PASS|FAIL|SKIP
  local name="$1"; shift
  local json="$RESULTS/${name}.json"
  local status
  status=$("$BIN/$name" "$@" --out "$json" 2>"$RESULTS/${name}.err" \
             | awk -F= '/^PROBE_RESULT=/{print $2; exit}')
  echo "$status"
}

echo "=== probe_single_model (baseline) ==="
SINGLE=$(run_probe probe_single_model \
  --model-json "$MODEL_A_JSON" --model-raw "$MODEL_A_RAW" --out-count 12 \
  --warmup "$WARMUP" --frames "$FRAMES" --rounds "$ROUNDS")
echo "single_model: $SINGLE"

echo "=== probe_two_networks (residency) ==="
TWO=$(run_probe probe_two_networks \
  --model-a-json "$MODEL_A_JSON" --model-a-raw "$MODEL_A_RAW" \
  --model-b-json "$MODEL_B_JSON" --model-b-raw "$MODEL_B_RAW" \
  --warmup "$WARMUP" --frames "$FRAMES")
echo "two_networks: $TWO"

echo "=== probe_sequential_inference (A->B->A serial, no re-open) ==="
SEQ=$(run_probe probe_sequential_inference \
  --model-a-json "$MODEL_A_JSON" --model-a-raw "$MODEL_A_RAW" \
  --model-b-json "$MODEL_B_JSON" --model-b-raw "$MODEL_B_RAW" \
  --warmup "$WARMUP" --frames "$FRAMES")
echo "sequential: $SEQ"

echo "=== probe_concurrent_inference (SDK-gated) ==="
CONC=$(run_probe probe_concurrent_inference)
echo "concurrent: $CONC"

echo "=== probe_unload_reload (switch only) ==="
UNLOAD=$(run_probe probe_unload_reload \
  --model-a-json "$MODEL_A_JSON" --model-a-raw "$MODEL_A_RAW" \
  --model-b-json "$MODEL_B_JSON" --model-b-raw "$MODEL_B_RAW" \
  --warmup "$WARMUP" --frames "$FRAMES")
echo "unload_reload: $UNLOAD"

# ---- provisional conclusion classification (A/B/C/D/E per task section 6) ----
# D is deliberately unreachable here: the SDK DOCS document multi-network
# (audit section 5), so "SDK + measurement both prove single-model-only" cannot
# hold.  A failing baseline forces E (unresolved).
CONCL="E:MULTI_MODEL_CAPABILITY_UNRESOLVED"
if [ "$SINGLE" = "PASS" ]; then
  if [ "$TWO" = "PASS" ] && [ "$SEQ" = "PASS" ]; then
    if [ "$CONC" = "PASS" ]; then
      CONCL="B:MULTI_MODEL_CONCURRENT_SUPPORTED"
    else
      CONCL="A:MULTI_MODEL_RESIDENT_SUPPORTED"
    fi
  elif [ "$UNLOAD" = "PASS" ]; then
    CONCL="C:MULTI_MODEL_SWITCH_ONLY"
  else
    CONCL="E:MULTI_MODEL_CAPABILITY_UNRESOLVED"
  fi
fi

{
  echo "M27.1 board probe summary"
  echo "========================="
  echo "single_model=$SINGLE two_networks=$TWO sequential=$SEQ concurrent=$CONC unload_reload=$UNLOAD"
  echo "FINAL_CONCLUSION=$CONCL"
} | tee "$RESULTS/M27_1_FINAL_CONCLUSION.txt"

echo ""
echo "Per-probe result JSON: $RESULTS/*.json"
echo "Conclusion file:        $RESULTS/M27_1_FINAL_CONCLUSION.txt"
