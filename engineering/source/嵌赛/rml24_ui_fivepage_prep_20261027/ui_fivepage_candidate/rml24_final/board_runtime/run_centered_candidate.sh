#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 --run DIR --legacy-root DIR --model-dir DIR [--control-host IP] [--initial-mode FIXED|BAND_SCAN] [--scan-start-hz HZ --scan-stop-hz HZ --scan-step-hz HZ] [--save]" >&2
}

RUN=""
LEGACY_ROOT=""
MODEL_DIR=""
CONTROL_HOST="192.168.126.10"
INITIAL_MODE="FIXED"
SCAN_START="2395000000"
SCAN_STOP="2405000000"
SCAN_STEP="1000000"
SAVE_ARGS=()
while [ "$#" -gt 0 ]; do
  case "$1" in
    --run) RUN="$2"; shift 2 ;;
    --legacy-root) LEGACY_ROOT="$2"; shift 2 ;;
    --model-dir) MODEL_DIR="$2"; shift 2 ;;
    --control-host) CONTROL_HOST="$2"; shift 2 ;;
    --initial-mode) INITIAL_MODE="$2"; shift 2 ;;
    --scan-start-hz) SCAN_START="$2"; shift 2 ;;
    --scan-stop-hz) SCAN_STOP="$2"; shift 2 ;;
    --scan-step-hz) SCAN_STEP="$2"; shift 2 ;;
    --save) SAVE_ARGS=(--save-raw --save-tensor); shift ;;
    *) usage; exit 2 ;;
  esac
done

[ -n "$RUN" ] && [ -n "$LEGACY_ROOT" ] && [ -n "$MODEL_DIR" ] || { usage; exit 2; }
[ "$INITIAL_MODE" = FIXED ] || [ "$INITIAL_MODE" = BAND_SCAN ] || { usage; exit 2; }
[ ! -e "$RUN" ] || { echo "run directory already exists: $RUN" >&2; exit 2; }
[ -x "$LEGACY_ROOT/build/npu_stream" ] || { echo "missing npu_stream" >&2; exit 2; }
[ -f "$LEGACY_ROOT/pluto_link_probe.py" ] || { echo "missing pluto_link_probe.py" >&2; exit 2; }
[ -f "$LEGACY_ROOT/pilot_recovery.py" ] || { echo "missing pilot_recovery.py" >&2; exit 2; }
[ -f "$MODEL_DIR/rml24_adamrv11_bf16.json" ] || { echo "missing model json" >&2; exit 2; }
[ -f "$MODEL_DIR/rml24_adamrv11_bf16.raw" ] || { echo "missing model raw" >&2; exit 2; }

echo '28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42  '"$MODEL_DIR/rml24_adamrv11_bf16.json" | sha256sum -c -
echo 'c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151  '"$MODEL_DIR/rml24_adamrv11_bf16.raw" | sha256sum -c -
ROOT=$(cd "$(dirname "$0")/.." && pwd)
echo 'e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a  '"$ROOT/recovery/candidate_two_dc.py" | sha256sum -c -

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

env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
  python3 "$ROOT/board_runtime/rml24_dualmode_receiver_centered_candidate.py" \
    --npu-socket "$RUN/npu.sock" \
    --ui-socket "${UI_SOCKET:-/run/sdr_amr_ui_rml24_final.sock}" \
    --ui-control-socket "${UI_CONTROL_SOCKET:-/run/sdr_amr_control_rml24_final.sock}" \
    --out "$RUN/capture" \
    --legacy-root "$LEGACY_ROOT" \
    --control-host "$CONTROL_HOST" \
    --initial-mode "$INITIAL_MODE" \
    --scan-start-hz "$SCAN_START" \
    --scan-stop-hz "$SCAN_STOP" \
    --scan-step-hz "$SCAN_STEP" \
    "${SAVE_ARGS[@]}"

wait "$NPU_PID"
trap - EXIT
grep -ao 'NPU_STREAM_STOP[^[:cntrl:]]*' "$RUN/npu.log"
echo "RML24_DUALMODE_RUN result=PASS initial_mode=$INITIAL_MODE run=$RUN"

