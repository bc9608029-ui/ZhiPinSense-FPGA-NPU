#!/usr/bin/env bash
set -euo pipefail
ROOT=/root/rml24_mainchain_diagnostic_20261028
MODEL=/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16
OUT="$ROOT/gmsk_mean_replay02"
test ! -e "$OUT"
systemctl stop rml24-receiver
mkdir "$OUT"
/root/amr_rescue_20261025/build/npu_stream "$MODEL/rml24_adamrv11_bf16.json" "$MODEL/rml24_adamrv11_bf16.raw" "$OUT/npu.sock" > "$OUT/npu.log" 2>&1 &
NPU=$!
cleanup(){ kill "$NPU" 2>/dev/null || true; wait "$NPU" 2>/dev/null || true; systemctl start rml24-receiver; }
trap cleanup EXIT
for i in $(seq 1 100); do test -S "$OUT/npu.sock" && break; kill -0 "$NPU"; sleep .1; done
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3 "$ROOT/replay_gmsk_mean.py"
wait "$NPU"
systemctl start rml24-receiver
trap - EXIT
grep -ao 'NPU_STREAM_STOP[^[:cntrl:]]*' "$OUT/npu.log"
