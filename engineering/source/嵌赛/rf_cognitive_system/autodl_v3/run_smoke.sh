#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
python -m pytest tests/test_qam_aware_rfnet_v3.py -q
python -m evaluation.audit_qam_aware_v3_dataset --config configs/qam_aware_v3_smoke.yaml
python -m training.train_qam_aware_v3 --config configs/qam_aware_v3_smoke.yaml
python -m evaluation.evaluate_qam_aware_v3 --config configs/qam_aware_v3_smoke.yaml
python -m scripts.export_qam_aware_v3_onnx --config configs/qam_aware_v3_smoke.yaml
mkdir -p outputs/qam_aware_v3/smoke
touch outputs/qam_aware_v3/smoke/V3_AUTODL_SMOKE_PASS
echo "V3_AUTODL_SMOKE_PASS"
