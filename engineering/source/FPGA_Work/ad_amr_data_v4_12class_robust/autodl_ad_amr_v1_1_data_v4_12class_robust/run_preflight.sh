#!/usr/bin/env bash
set -euo pipefail
export CUBLAS_WORKSPACE_CONFIG=:4096:8

# 鲁棒性 fine-tune 从十二类正式 best.pt 初始化，必须真实存在（否则 fail closed）。
for SEED in 2026 2027; do
  test -f "outputs/ad_amr_v1_1_data_v3_12class/formal/seed${SEED}/checkpoints/best.pt" || {
    echo "Missing twelve-class formal best.pt for seed ${SEED}" >&2
    echo "Unpack the twelve-class formal results into outputs/ad_amr_v1_1_data_v3_12class first." >&2
    exit 2
  }
done

echo "[preflight 1/2] complete source suite"
python -m pytest tests -q --basetemp=.pytest_tmp_data_v4_12class_robust
echo "[preflight 2/2] robustness init/resume/eval/ONNX on real CUDA"
python -u -m scripts.run_ad_amr_v1_1_data_v4_12class_robust_cuda_preflight
