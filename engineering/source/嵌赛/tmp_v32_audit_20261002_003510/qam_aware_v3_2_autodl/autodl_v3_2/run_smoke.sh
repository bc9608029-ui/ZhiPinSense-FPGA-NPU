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
  tests/test_qam_aware_rfnet_v3_2.py \
  tests/test_qam_aware_v3_2_trainer.py \
  tests/test_qam_aware_v3_2_resume.py \
  tests/test_qam_aware_v3_2_acceptance.py \
  tests/test_qam_aware_v3_2_onnx_gate.py \
  tests/test_resumable_trainer.py \
  tests/test_qam_aware_rfnet_v3.py \
  -q
python -m evaluation.audit_qam_aware_v3_2_dataset --config configs/qam_aware_v3_2_smoke.yaml
python -m training.train_qam_aware_v3_2 --config configs/qam_aware_v3_2_smoke.yaml
python -m evaluation.evaluate_qam_aware_v3_2 --config configs/qam_aware_v3_2_smoke.yaml
python -m scripts.export_qam_aware_v3_2_onnx --config configs/qam_aware_v3_2_smoke.yaml
mkdir -p outputs/qam_aware_v3_2/smoke
touch outputs/qam_aware_v3_2/smoke/V3_2_AUTODL_SMOKE_PASS
echo "V3_2_AUTODL_SMOKE_PASS"
