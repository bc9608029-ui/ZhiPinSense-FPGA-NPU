#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
# CUDA determinism: pin cuBLAS to a reproducible algorithm before any Python
# process starts, so strict-resume and smoke results are bit-reproducible.
export CUBLAS_WORKSPACE_CONFIG=:4096:8

# The resumable-trainer and resume tests guard the strict-resume contract that
# the checkpoint-metric / minimum-epochs / CUDA-determinism code paths touch.
python -m pytest \
  tests/test_qam_aware_rfnet_v3_1.py \
  tests/test_qam_aware_v3_1_trainer.py \
  tests/test_qam_aware_v3_1_resume.py \
  tests/test_qam_aware_v3_1_acceptance.py \
  tests/test_resumable_trainer.py \
  tests/test_qam_aware_rfnet_v3.py \
  -q
python -m evaluation.audit_qam_aware_v3_1_dataset --config configs/qam_aware_v3_1_smoke.yaml
python -m training.train_qam_aware_v3_1 --config configs/qam_aware_v3_1_smoke.yaml
python -m evaluation.evaluate_qam_aware_v3_1 --config configs/qam_aware_v3_1_smoke.yaml
python -m scripts.export_qam_aware_v3_1_onnx --config configs/qam_aware_v3_1_smoke.yaml
mkdir -p outputs/qam_aware_v3_1/smoke
touch outputs/qam_aware_v3_1/smoke/V3_1_AUTODL_SMOKE_PASS
echo "V3_1_AUTODL_SMOKE_PASS"
