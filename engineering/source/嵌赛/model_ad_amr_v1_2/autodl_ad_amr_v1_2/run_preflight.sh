#!/usr/bin/env bash
set -euo pipefail
export CUBLAS_WORKSPACE_CONFIG=:4096:8

echo "[preflight 1/3] complete V1.2 source suite"
python -m pytest tests -q --basetemp=.pytest_tmp_v1_2
echo "[preflight 2/3] fixed-batch trainability probe"
python -u -m scripts.overfit_probe_v1_1
echo "[preflight 3/3] real CUDA curriculum/train/resume/OOD/eval/strict ONNX gate"
python -u -m scripts.run_ad_amr_v1_2_cuda_preflight
