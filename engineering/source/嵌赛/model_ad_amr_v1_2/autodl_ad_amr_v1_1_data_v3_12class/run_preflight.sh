#!/usr/bin/env bash
set -euo pipefail
export CUBLAS_WORKSPACE_CONFIG=:4096:8

test -f data/radioml2018/audit.json
test -f data/radioml2018/split_indices.npz
echo "[preflight 1/2] complete source suite"
python -m pytest tests -q --basetemp=.pytest_tmp_data_v3_12class
echo "[preflight 2/2] 12-class overfit/CUDA/resume/transfer/eval/ONNX"
python -u -m scripts.run_ad_amr_v1_1_data_v3_12class_cuda_preflight
