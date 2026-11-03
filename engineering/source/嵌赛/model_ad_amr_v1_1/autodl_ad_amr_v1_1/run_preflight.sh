#!/usr/bin/env bash
set -euo pipefail
export CUBLAS_WORKSPACE_CONFIG=:4096:8

echo "[preflight 1/3] complete source suite"
python -m pytest tests -q --basetemp=.pytest_tmp_v1_1
echo "[preflight 2/3] fixed-batch trainability probe"
python -u -m scripts.overfit_probe_v1_1
echo "[preflight 3/3] real CUDA train/resume/full-SNR/eval/strict ONNX gate"
python -u -m scripts.run_ad_amr_v1_1_cuda_preflight
