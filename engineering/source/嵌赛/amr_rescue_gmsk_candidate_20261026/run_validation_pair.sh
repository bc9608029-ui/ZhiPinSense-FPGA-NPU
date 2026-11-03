#!/usr/bin/env bash
set -euo pipefail
RUN="$1"
test ! -e "$RUN"
mkdir "$RUN"
FROZEN=/root/amr_rescue_20261025
MODEL=/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16
"$FROZEN/build/npu_stream" "$MODEL/rml24_adamrv11_bf16.json" "$MODEL/rml24_adamrv11_bf16.raw" "$RUN/npu.sock" > "$RUN/npu.log" 2>&1 &
NPU_PID=$!
cleanup(){ if kill -0 "$NPU_PID" 2>/dev/null; then kill "$NPU_PID"; fi; wait "$NPU_PID" 2>/dev/null || true; }
trap cleanup EXIT
for attempt in $(seq 1 100); do
 [ -S "$RUN/npu.sock" ] && break
 kill -0 "$NPU_PID" || exit 1
 sleep .1
done
test -S "$RUN/npu.sock"
env OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python /root/amr_rescue_gmsk_candidate_20261026/paired_board_rx_two_dc.py --socket "$RUN/npu.sock" --out "$RUN/capture"
wait "$NPU_PID"
grep -ao 'NPU_STREAM_STOP[^[:cntrl:]]*' "$RUN/npu.log"