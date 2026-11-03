#!/usr/bin/env bash
set -euo pipefail
ROOT=/root/rml24_standalone_execution_20261027
MODEL=/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16
OUT="$ROOT/clean_npu_probe"
test ! -e "$OUT"
mkdir "$OUT"
echo '28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42  '"$MODEL/rml24_adamrv11_bf16.json" | sha256sum -c -
echo 'c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151  '"$MODEL/rml24_adamrv11_bf16.raw" | sha256sum -c -
/root/amr_rescue_20261025/build/npu_stream "$MODEL/rml24_adamrv11_bf16.json" "$MODEL/rml24_adamrv11_bf16.raw" "$OUT/npu.sock" > "$OUT/npu.log" 2>&1 &
NPU=$!
cleanup(){ kill "$NPU" 2>/dev/null || true; wait "$NPU" 2>/dev/null || true; }
trap cleanup EXIT
for i in $(seq 1 100); do
  test -S "$OUT/npu.sock" && break
  kill -0 "$NPU"
  sleep .1
done
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3 "$ROOT/run_clean_npu_probe.py"
wait "$NPU"
trap - EXIT
grep -ao 'NPU_STREAM_STOP[^[:cntrl:]]*' "$OUT/npu.log"
