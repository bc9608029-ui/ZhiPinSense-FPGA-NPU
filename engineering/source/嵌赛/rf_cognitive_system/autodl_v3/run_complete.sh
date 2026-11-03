#!/usr/bin/env bash
set -euo pipefail

# One-command AutoDL workflow. It is safe to rerun after an interrupted job:
# formal training resumes from last.pt when that checkpoint exists.
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"

FORMAL_ROOT="outputs/qam_aware_v3/formal"
SMOKE_MARKER="outputs/qam_aware_v3/smoke/V3_AUTODL_SMOKE_PASS"
LAST_CHECKPOINT="${FORMAL_ROOT}/checkpoints/last.pt"
LOG_DIR="${FORMAL_ROOT}/logs"
mkdir -p "$LOG_DIR"

echo "[1/7] Checking CUDA and installing non-Torch dependencies"
bash autodl_v3/setup_env.sh

echo "[2/7] Running source tests and deployment/export smoke test"
if [[ -f "$SMOKE_MARKER" ]]; then
  echo "Smoke marker exists; keeping the previously passed smoke result."
else
  bash autodl_v3/run_smoke.sh
  mkdir -p "$(dirname "$SMOKE_MARKER")"
  touch "$SMOKE_MARKER"
fi

echo "[3/7] Auditing the formal synthetic dataset contract"
python -m evaluation.audit_qam_aware_v3_dataset --config configs/qam_aware_v3.yaml

echo "[4/7] Training V3 (automatic strict resume when last.pt exists)"
if [[ -f "$LAST_CHECKPOINT" ]]; then
  echo "Resuming formal training from $LAST_CHECKPOINT"
  python -m training.train_qam_aware_v3 \
    --config configs/qam_aware_v3.yaml \
    --resume "$LAST_CHECKPOINT" \
    2>&1 | tee -a "$LOG_DIR/autodl_console.log"
else
  echo "Starting a clean formal trajectory"
  python -m training.train_qam_aware_v3 \
    --config configs/qam_aware_v3.yaml \
    2>&1 | tee "$LOG_DIR/autodl_console.log"
fi

echo "[5/7] Running robust and exact V2-compatible evaluation"
python -m evaluation.evaluate_qam_aware_v3 --config configs/qam_aware_v3.yaml

echo "[6/7] Exporting deployment-compatible ONNX graphs"
python -m scripts.export_qam_aware_v3_onnx --config configs/qam_aware_v3.yaml

echo "[7/7] Applying promotion gates and packaging all formal artifacts"
ACCEPTANCE_RC=0
python -m evaluation.check_qam_aware_v3_acceptance || ACCEPTANCE_RC=$?
python -m scripts.package_qam_aware_v3_results

if [[ "$ACCEPTANCE_RC" -eq 0 ]]; then
  echo "V3_AUTODL_COMPLETE_PASS"
  echo "Download: outputs/qam_aware_v3/qam_aware_v3_formal_results.tar.gz"
  exit 0
fi

echo "V3_AUTODL_COMPLETE_TRAINED_BUT_GATE_FAILED"
echo "Training/evaluation/export completed, but V3 remains a challenger and V2 stays frozen as champion."
echo "Download the result archive for diagnosis: outputs/qam_aware_v3/qam_aware_v3_formal_results.tar.gz"
exit "$ACCEPTANCE_RC"
