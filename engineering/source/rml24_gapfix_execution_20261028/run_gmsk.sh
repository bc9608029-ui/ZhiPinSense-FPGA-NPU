#!/usr/bin/env bash
set -euo pipefail
ROOT=/root/rml24_mainchain_diagnostic_20261028
RUN="$ROOT/diag_gmsk02"
MODEL=/root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16
BASE=/root/rml24_standalone_execution_20261027/candidate/rml24_final
test ! -e "$RUN"
systemctl stop rml24-receiver
trap 'systemctl start rml24-receiver' EXIT
echo 'e0aa12029e9c5aa670a9340d9c078814b10dcfb0ee82c580adaad4f55affcf3a  '"$BASE/recovery/candidate_two_dc.py" | sha256sum -c -
echo 'cb529824a80e9fa2aea6aaa31375c8d560f117c36b9644862cb459f6c39cd79a  '"$BASE/runtime/receiver_core.py" | sha256sum -c -
echo '28272abc054b26a58d4fa9301b7d65cc5dc40b248abd8924d4900b8e58a14a42  '"$MODEL/rml24_adamrv11_bf16.json" | sha256sum -c -
echo 'c1781aec264f38e2cab32a23ccb3d77f30230c3a369f9b19a9234de9dc8b9151  '"$MODEL/rml24_adamrv11_bf16.raw" | sha256sum -c -
mkdir "$RUN"
/root/amr_rescue_20261025/build/npu_stream "$MODEL/rml24_adamrv11_bf16.json" "$MODEL/rml24_adamrv11_bf16.raw" "$RUN/npu.sock" > "$RUN/npu.log" 2>&1 &
NPU=$!
cleanup(){ kill "$NPU" 2>/dev/null || true; wait "$NPU" 2>/dev/null || true; systemctl start rml24-receiver; }
trap cleanup EXIT
for i in $(seq 1 100); do test -S "$RUN/npu.sock" && break; kill -0 "$NPU"; sleep .1; done
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 /root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3 "$ROOT/observe_gmsk.py" \
  --legacy-root /root/amr_rescue_20261025 --npu-socket "$RUN/npu.sock" --out "$RUN/capture" \
  --ui-socket '' --ui-control-socket /run/rml24_diag_control.sock --duration-sec 140 --initial-mode FIXED
wait "$NPU"
systemctl start rml24-receiver
trap - EXIT
grep -ao 'NPU_STREAM_STOP[^[:cntrl:]]*' "$RUN/npu.log"
