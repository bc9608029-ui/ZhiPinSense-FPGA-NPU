#!/usr/bin/env bash
set -euo pipefail
BASE="$(cd "$(dirname "$0")" && pwd)"
ORIGINAL_ROOT="${ORIGINAL_ROOT:-/root/realrf_finetune_pilot1_test_1773373090}"
PYTHON="${AMR_PYTHON:-/root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python}"
SERVER="${1:-192.168.126.50}"
RUN_DIR="$(mktemp -d /tmp/amr_rescue_run.XXXXXX)"
MODEL_JSON="$ORIGINAL_ROOT/model_rml24_bf16/rml24_adamrv11_bf16.json"
MODEL_RAW="$ORIGINAL_ROOT/model_rml24_bf16/rml24_adamrv11_bf16.raw"
actual="$(sha256sum "$MODEL_RAW" | cut -d ' ' -f 1)"
test "$actual" = c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151
actual="$(sha256sum "$MODEL_JSON" | cut -d ' ' -f 1)"
test "$actual" = 28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42
if [ ! -x "$BASE/build/npu_stream" ]; then
  cmake -S "$BASE" -B "$BASE/build" -DCMAKE_PREFIX_PATH=/usr/cmake -DORIGINAL_ROOT="$ORIGINAL_ROOT"
  cmake --build "$BASE/build" -j1
fi
"$BASE/build/npu_stream" "$MODEL_JSON" "$MODEL_RAW" "$RUN_DIR/npu.sock" > "$RUN_DIR/npu.log" 2>&1 &
NPU_PID=$!
cleanup() {
  if kill -0 "$NPU_PID" 2>/dev/null; then kill "$NPU_PID"; fi
  wait "$NPU_PID" 2>/dev/null || true
  echo "RESULT_DIR=$RUN_DIR"
}
trap cleanup EXIT
for attempt in $(seq 1 100); do
  [ -S "$RUN_DIR/npu.sock" ] && break
  kill -0 "$NPU_PID" || { cat "$RUN_DIR/npu.log"; exit 1; }
  sleep 0.1
done
test -S "$RUN_DIR/npu.sock"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1
"$PYTHON" "$BASE/board_live_rx.py" --server "$SERVER" --socket "$RUN_DIR/npu.sock" --out "$RUN_DIR/capture" 2>&1 | tee "$RUN_DIR/rx.log"
wait "$NPU_PID"
grep -ao 'NPU_STREAM_STOP[^[:cntrl:]]*' "$RUN_DIR/npu.log"
