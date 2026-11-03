#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
# The resumable-trainer test guards the strict-resume contract that the
# checkpoint-metric / minimum-epochs code paths touch.
python -m pytest tests/test_qam_aware_rfnet_v3_1.py tests/test_resumable_trainer.py -q
python -m evaluation.audit_qam_aware_v3_1_dataset --config configs/qam_aware_v3_1_smoke.yaml
python -m training.train_qam_aware_v3_1 --config configs/qam_aware_v3_1_smoke.yaml
python -m evaluation.evaluate_qam_aware_v3_1 --config configs/qam_aware_v3_1_smoke.yaml
python -m scripts.export_qam_aware_v3_1_onnx --config configs/qam_aware_v3_1_smoke.yaml
mkdir -p outputs/qam_aware_v3_1/smoke
touch outputs/qam_aware_v3_1/smoke/V3_1_AUTODL_SMOKE_PASS
echo "V3_1_AUTODL_SMOKE_PASS"
