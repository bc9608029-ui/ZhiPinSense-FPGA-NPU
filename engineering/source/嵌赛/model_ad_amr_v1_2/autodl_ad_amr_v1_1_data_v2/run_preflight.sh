#!/usr/bin/env bash
set -euo pipefail
export CUBLAS_WORKSPACE_CONFIG=:4096:8

test -f data/radioml2018/audit.json
test -f data/radioml2018/split_indices.npz
echo "[preflight 1/3] complete source suite"
python -m pytest tests -q --basetemp=.pytest_tmp_data_v2
echo "[preflight 2/3] fixed-batch V1.1 trainability probe"
python -u -m scripts.overfit_probe_v1_1
echo "[preflight 3/3] CUDA public-pretrain/resume/transfer/target-resume/eval/ONNX"
python -u -m scripts.run_ad_amr_v1_1_data_v2_cuda_preflight

