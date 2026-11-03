#!/usr/bin/env bash
set -euo pipefail

# Rehearse the complete V3.2 pipeline with tiny configs:
# ablation -> selection -> three-seed formal -> aggregate -> gate -> package.
# The gate is expected to FAIL here (an untrained model does not clear the
# promotion bars), so the script completes and reports the gate result rather
# than treating a gate failure as a hard error.
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export CUBLAS_WORKSPACE_CONFIG=:4096:8

SMOKE_ROOT="outputs/qam_aware_v3_2/smoke"
ABLATION_SUMMARY="$SMOKE_ROOT/ablation/ablation_summary.json"
SELECTED="$SMOKE_ROOT/formal/selected_candidate.yaml"
LOG_DIR="$SMOKE_ROOT/formal/logs"
mkdir -p "$LOG_DIR"

echo "[1/4] Tiny ablation (A1-A3)"
python -m training.train_qam_aware_v3_2_ablation --config configs/qam_aware_v3_2_ablation_smoke.yaml

echo "[2/4] Freeze the validation-only winner"
python -m training.select_qam_aware_v3_2_candidate --summary "$ABLATION_SUMMARY" --out "$SELECTED"

echo "[3/4] Tiny three-seed formal (per-seed resume/skip + multi-seed gate)"
set +o pipefail
python -m scripts.run_qam_aware_v3_2_formal \
  --config configs/qam_aware_v3_2_smoke_full.yaml \
  --selected "$SELECTED" \
  --seeds 2026 2027 2028 \
  --formal-root "$SMOKE_ROOT/formal" \
  --gates configs/qam_aware_v3_2_acceptance.yaml \
  2>&1 | tee -a "$LOG_DIR/autodl_smoke_console.log"
SMOKE_FORMAL_RC=${PIPESTATUS[0]}
set -o pipefail
if [[ "$SMOKE_FORMAL_RC" -ne 0 && "$SMOKE_FORMAL_RC" -ne 2 ]]; then
  echo "Smoke formal run failed with exit code $SMOKE_FORMAL_RC" >&2
  exit "$SMOKE_FORMAL_RC"
fi

echo "[4/4] Package the smoke results"
python -m scripts.package_qam_aware_v3_2_results \
  --formal-root "$SMOKE_ROOT/formal" \
  --manifest "$SMOKE_ROOT/smoke_formal_results_sha256.txt" \
  --archive "$SMOKE_ROOT/qam_aware_v3_2_smoke_formal_results.tar.gz" \
  --package-json "$SMOKE_ROOT/smoke_formal_results_package.json"

echo "V3_2_AUTODL_SMOKE_FULL_PASS (gate_result=$SMOKE_FORMAL_RC)"
