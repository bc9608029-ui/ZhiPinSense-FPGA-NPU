#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 --run DIR --legacy-root DIR --model-dir DIR [--control-host IP] [--paired] [--save]" >&2
}

RUN=""
LEGACY_ROOT=""
MODEL_DIR=""
CONTROL_HOST="192.168.126.50"
MODE="candidate"
SAVE_ARGS=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --run) RUN="$2"; shift 2 ;;
    --legacy-root) LEGACY_ROOT="$2"; shift 2 ;;
    --model-dir) MODEL_DIR="$2"; shift 2 ;;
    --control-host) CONTROL_HOST="$2"; shift 2 ;;
    --paired) MODE="paired"; shift ;;
    --save) SAVE_ARGS=(--save-raw --save-tensor); shift ;;
    *) usage; exit 2 ;;
  esac
done

[ -n "$RUN" ] && [ -n "$LEGACY_ROOT" ] && [ -n "$MODEL_DIR" ] || { usage; exit 2; }
[ ! -e "$RUN" ] || { echo "run directory already exists: $RUN" >&2; exit 2; }
[ -x "$LEGACY_ROOT/build/npu_stream" ] || { echo "missing npu_stream" >&2; exit 2; }
[ -f "$LEGACY_ROOT/pluto_link_probe.py" ] || { echo "missing pluto_link_probe.py" >&2; exit 2; }
[ -f "$LEGACY_ROOT/pilot_recovery.py" ] || { echo "missing pilot_recovery.py" >&2; exit 2; }
[ -f "$MODEL_DIR/rml24_adamrv11_bf16.json" ] || { echo "missing model json" >&2; exit 2; }
[ -f "$MODEL_DIR/rml24_adamrv11_bf16.raw" ] || { echo "missing model raw" >&2; exit 2; }

echo '28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42  '"$MODEL_DIR/rml24_adamrv11_bf16.json" | sha256sum -c -
echo 'c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151  '"$MODEL_DIR/rml24_adamrv11_bf16.raw" | sha256sum -c -
echo 'e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a  '"$(cd "$(dirname "$0")/.." && pwd)/recovery/candidate_two_dc.py" | sha256sum -c -

mkdir "$RUN"
"$LEGACY_ROOT/build/npu_stream" \
  "$MODEL_DIR/rml24_adamrv11_bf16.json" \
  "$MODEL_DIR/rml24_adamrv11_bf16.raw" \
  "$RUN/npu.sock" > "$RUN/npu.log" 2>&1 &
NPU_PID=$!
cleanup() {
  if kill -0 "$NPU_PID" 2>/dev/null; then kill "$NPU_PID"; fi
  wait "$NPU_PID" 2>/dev/null || true
}
trap cleanup EXIT
for _ in $(seq 1 100); do
  [ -S "$RUN/npu.sock" ] && break
  kill -0 "$NPU_PID" || { echo "npu_stream exited during startup" >&2; exit 1; }
  sleep 0.1
done
[ -S "$RUN/npu.sock" ] || { echo "npu socket not ready" >&2; exit 1; }

ROOT=$(cd "$(dirname "$0")/.." && pwd)
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python3 "$ROOT/board_runtime/rml24_final_receiver.py" \
    --npu-socket "$RUN/npu.sock" \
    --out "$RUN/capture" \
    --legacy-root "$LEGACY_ROOT" \
    --control-host "$CONTROL_HOST" \
    --mode "$MODE" \
    "${SAVE_ARGS[@]}"

wait "$NPU_PID"
trap - EXIT
grep -ao 'NPU_STREAM_STOP[^[:cntrl:]]*' "$RUN/npu.log"
echo "RML24_FINAL_RUN result=PASS mode=$MODE run=$RUN"

