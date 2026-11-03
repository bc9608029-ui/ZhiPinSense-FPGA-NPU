#!/bin/bash
set -euo pipefail
export PATH=/root/miniconda3/envs/torch_v2.0.1_aarch64/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
export UI_SOCKET=/run/sdr_amr_ui_rml24_final.sock
for n in $(seq 1 60); do
 [ -S "$UI_SOCKET" ] && break
 sleep .5
done
[ -S "$UI_SOCKET" ]
if pgrep -x npu_stream >/dev/null; then echo 'Another NPU session is active; refusing a duplicate' >&2; exit 1; fi
mkdir -p /var/log/rml24/runs
RUN=/var/log/rml24/runs/$(date -u +%Y%m%dT%H%M%S)-$$
echo "RML24_RECEIVER_ATTEMPT run=$RUN control=192.168.126.50:39012"
exec bash /opt/rml24-system/rml24_final/board_runtime/run_final_receiver.sh --run "$RUN" --legacy-root /root/amr_rescue_20261025 --model-dir /root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16 --control-host 192.168.126.50
