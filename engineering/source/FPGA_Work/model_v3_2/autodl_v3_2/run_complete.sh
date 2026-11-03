#!/usr/bin/env bash
set -euo pipefail

# One-command V3.2 workflow.  Safe to re-run after an interruption:
#   * a completed seed is skipped (its SEED_DONE.json marker exists);
#   * an incomplete seed resumes from its own checkpoints/last.pt;
#   * the frozen selected_candidate.yaml is never re-derived or silently changed;
#   * PASS is printed only after every seed, the multi-seed gate and packaging
#     all complete.
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export CUBLAS_WORKSPACE_CONFIG=:4096:8

ROOT="outputs/qam_aware_v3_2"
SMOKE_MARKER="$ROOT/smoke/V3_2_AUTODL_SMOKE_PASS"
SELECTED="$ROOT/formal/selected_candidate.yaml"
ABLATION_SUMMARY="$ROOT/ablation/ablation_summary.json"
LOG_DIR="$ROOT/formal/logs"
mkdir -p "$LOG_DIR"

echo "[1/8] Checking CUDA and installing non-Torch dependencies"
bash autodl_v3_2/setup_env.sh

echo "[2/8] Running source tests and deployment/export smoke test"
if [[ -f "$SMOKE_MARKER" ]]; then
  echo "Smoke marker exists; keeping the previously passed smoke result."
else
  bash autodl_v3_2/run_smoke.sh
  mkdir -p "$(dirname "$SMOKE_MARKER")"
  touch "$SMOKE_MARKER"
fi

echo "[3/8] Auditing the formal synthetic dataset contract"
python -m evaluation.audit_qam_aware_v3_2_dataset --config configs/qam_aware_v3_2.yaml

echo "[4/8] Running controlled ablations (A1-A3) and freezing the validation-only winner"
if [[ -f "$SELECTED" ]]; then
  echo "selected_candidate.yaml already frozen; skipping ablation + selection."
else
  if [[ ! -f "$ABLATION_SUMMARY" ]]; then
    bash autodl_v3_2/run_ablation.sh
  else
    echo "ablation_summary.json already present; reusing it for selection."
  fi
  python -m training.select_qam_aware_v3_2_candidate \
    --summary "$ABLATION_SUMMARY" \
    --out "$SELECTED"
fi

echo "[5/8] Verifying the zero-gate initialization reproduces V2 exactly"
python -m scripts.verify_qam_aware_v3_2_init --config configs/qam_aware_v3_2.yaml

echo "[6/8] Training the three-seed formal trajectory (per-seed resume/skip + multi-seed gate)"
set +o pipefail
python -m scripts.run_qam_aware_v3_2_formal \
  --config configs/qam_aware_v3_2.yaml \
  --selected "$SELECTED" \
  --gates configs/qam_aware_v3_2_acceptance.yaml \
  2>&1 | tee -a "$LOG_DIR/autodl_console.log"
FORMAL_RC=${PIPESTATUS[0]}
set -o pipefail
if [[ "$FORMAL_RC" -ne 0 && "$FORMAL_RC" -ne 2 ]]; then
  echo "Formal training failed with exit code $FORMAL_RC (see $LOG_DIR/autodl_console.log)" >&2
  exit "$FORMAL_RC"
fi
ACCEPTANCE_RC=$FORMAL_RC

echo "[7/8] Packaging all formal artifacts (per-seed + aggregate)"
python -m scripts.package_qam_aware_v3_2_results

echo "[8/8] Final status"
if [[ "$ACCEPTANCE_RC" -eq 0 ]]; then
  echo "V3_2_AUTODL_COMPLETE_PASS"
  echo "Download: $ROOT/qam_aware_v3_2_formal_results.tar.gz"
  exit 0
fi

echo "V3_2_AUTODL_COMPLETE_TRAINED_BUT_GATE_FAILED"
echo "Three-seed training/evaluation/export completed, but V3.2 remains a challenger and V2 stays frozen as champion."
echo "Download the result archive for diagnosis: $ROOT/qam_aware_v3_2_formal_results.tar.gz"
exit "$ACCEPTANCE_RC"
