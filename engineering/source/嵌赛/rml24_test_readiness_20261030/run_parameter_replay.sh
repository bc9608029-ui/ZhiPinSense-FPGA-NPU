#!/usr/bin/env bash
set -euo pipefail
# Positional inputs are explicit actual board paths; no implicit legacy root.
[[ $# == 6 || $# == 7 ]] || { echo 'usage: PY NPU_BIN MODEL_DIR RECOVERY CAPTURES NEW_RUN [SELECTION_JSON]'; exit 2; }
PY=$1; NPU=$2; MODEL=$3; RECOVERY=$4; CAPTURES=$5; RUN=$6
ROOT=$(cd -- "$(dirname -- "$0")" && pwd)
[[ -x "$PY" && -x "$NPU" && -d "$CAPTURES" && ! -e "$RUN" ]] || exit 2
printf '%s  %s\n' 28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42 "$MODEL/rml24_adamrv11_bf16.json" | sha256sum -c -
printf '%s  %s\n' c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151 "$MODEL/rml24_adamrv11_bf16.raw" | sha256sum -c -
mkdir -- "$RUN"
"$NPU" "$MODEL/rml24_adamrv11_bf16.json" "$MODEL/rml24_adamrv11_bf16.raw" "$RUN/npu.sock" > "$RUN/npu.log" 2>&1 &
NPID=$!
cleanup() { if kill -0 "$NPID" 2>/dev/null; then kill -TERM "$NPID"; fi; wait "$NPID" 2>/dev/null || true; }
trap cleanup EXIT
for ((i=0;i<200;i++)); do
 [[ -S "$RUN/npu.sock" ]] && break
 kill -0 "$NPID" || exit 1
 sleep .1
done
[[ -S "$RUN/npu.sock" ]] || exit 1
SELECT=()
[[ $# == 7 ]] && SELECT=(--selection "$7")
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 "$PY" -I "$ROOT/gain_tools/replay_repeats.py" --captures "$CAPTURES" --recovery "$RECOVERY" --out "$RUN/replay" --npu-socket "$RUN/npu.sock" "${SELECT[@]}"
echo 'PARAMETER_REPLAY_COMPLETE; score offline with fixed denominator'
