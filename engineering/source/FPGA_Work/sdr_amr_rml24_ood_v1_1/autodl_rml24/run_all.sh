#!/usr/bin/env bash
# RML24-OOD V1.1 — one-click AutoDL orchestration (17 logical steps, fail-closed).
#
# Runs the frozen pipeline end-to-end.  Every downstream step resolves the final
# checkpoint from final_checkpoint_manifest.json and re-verifies its SHA-256
# (resume-with-SHA-verification), so a partial re-run after a failure is safe: it
# either reuses a provenance-verified artifact or fails closed, never silently
# reuses a stale trial.
#
# Usage:
#   bash autodl_rml24/run_all.sh                 # full pipeline (OE skipped)
#   RUN_OE=1 bash autodl_rml24/run_all.sh        # include the gated OE+Energy phase
#
# Deterministic CUDA + unbuffered Python throughout (see cuda_preflight + trainer).
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"

export PYTHONUNBUFFERED=1
export CUBLAS_WORKSPACE_CONFIG="${CUBLAS_WORKSPACE_CONFIG:-:4096:8}"

RUN_ID="$(date +%Y%m%d_%H%M%S)_$$"
CONFIG="configs/rml24_base.yaml"
MANIFEST="runs/rml24_base/formal/final_checkpoint_manifest.json"
OOD_REPORT="runs/ood_baselines/ood_baselines.json"
THRESHOLD_MANIFEST="runs/ood_baselines/ood_threshold_manifest.json"
TOTAL=17
CURRENT_STEP=""

step() {
  CURRENT_STEP="$1"
  echo ""
  echo "============================================================"
  echo "[$RUN_ID] STEP $1/$TOTAL: $2"
  echo "============================================================"
}

fail() {
  echo "AUTODL_PIPELINE_RESULT result=FAIL step=${CURRENT_STEP:-?} run_id=$RUN_ID reason=$1" >&2
  exit 1
}
trap 'fail "command failed (step=${CURRENT_STEP:-?})"' ERR

mkdir -p runs/autodl_rml24

# ---- 1. setup: environment ----
step 1 "environment + dependency check"
"$PYTHON" - <<'PY' 2>&1
import sys, torch
print(f"python={sys.version.split()[0]} torch={torch.__version__} cuda={torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"gpu={torch.cuda.get_device_name(0)}")
try:
    import optuna; print(f"optuna={optuna.__version__}")
except ImportError:
    print("optuna=MISSING (pilot will fall back to the seeded NumPy sampler)")
try:
    import onnx, onnxruntime
    print(f"onnx={onnx.__version__} onnxruntime={onnxruntime.__version__}")
except ImportError:
    print("onnx/onnxruntime=MISSING")
PY

if [ "${RUN_PIP_INSTALL:-0}" = "1" ]; then
  echo "[setup] pip install -r requirements-lock.txt"
  pip install -r requirements-lock.txt
fi

# ---- 2. data audit ----
step 2 "data audit (HDF5 SHA-256 + frozen split + manifests + split_audit artifact)"
scripts/run_data_audit.sh

# ---- 3. leakage audit ----
step 3 "split leakage audit (offline, no-overlap + per-stratum artifact)"
"$PYTHON" -m pytest tests/test_split_no_overlap.py tests/test_split_audit_artifact.py \
  tests/test_data_contract_portable.py -q 2>&1

# ---- 4. offline smoke (single-batch overfit gate) ----
step 4 "single-batch overfit smoke gate"
scripts/run_smoke.sh

# ---- 5. CUDA preflight ----
step 5 "CUDA preflight (data identity / forward / loss-optimizer / optuna / micro-train / onnx / ood)"
scripts/run_cuda_preflight.sh

# ---- 6. offline test suite ----
step 6 "offline test suite"
scripts/run_tests.sh

# ---- 7. pilot (Optuna TPE, <=12 trials, 20 epochs) ----
step 7 "pilot (Optuna TPE, bounded trials)"
"$PYTHON" -m training.rml24_pilot --config "$CONFIG" --search-space configs/search_space_rml24.yaml

# ---- 8. candidate selection (dedupe by signature + rank) ----
step 8 "candidate selection (dedupe + rank, validation-only)"
PILOT_SEED="$("$PYTHON" -c 'import yaml,sys;print(yaml.safe_load(open(sys.argv[1],encoding="utf-8"))["search"]["pilot_seed"])' configs/search_space_rml24.yaml)"
"$PYTHON" -m training.rml24_select --config "$CONFIG" --search-space configs/search_space_rml24.yaml \
  --pilot-root "runs/rml24_base/pilot/seed$PILOT_SEED"

# ---- 9. formal multi-seed (1 candidate x 3 seeds x 80 epochs, provenance-verified resume) ----
step 9 "formal training (frozen budget 1x3, dedup/resume)"
"$PYTHON" -m training.rml24_formal --config "$CONFIG" --search-space configs/search_space_rml24.yaml \
  --candidates "runs/rml24_base/pilot/pilot_unique_candidates.json"

# ---- 10. final checkpoint manifest ----
step 10 "final checkpoint manifest (single frozen source of truth)"
[ -f "$MANIFEST" ] || fail "missing $MANIFEST"
"$PYTHON" scripts/_resolve_checkpoint.py "$MANIFEST"  # re-verify checkpoint SHA

# ---- 11. semantic OOD baselines (MSP/Entropy/MaxLogit/Energy; no training) ----
step 11 "semantic OOD baselines (thresholds locked on ood_validation)"
scripts/run_ood_baselines.sh "$MANIFEST"

# ---- 12. OE+Energy (optional, gated 1+2 seed promotion) ----
step 12 "OE+Energy (optional; set RUN_OE=1 to enable)"
if [ "${RUN_OE:-0}" = "1" ]; then
  scripts/run_oe_energy.sh
else
  echo "[oe] skipped (RUN_OE=0); Energy baseline retained"
fi

# ---- 13. threshold calibration/freeze ----
step 13 "threshold freeze (write-once ood_threshold_manifest.json)"
"$PYTHON" -m scripts.run_threshold_freeze --manifest "$MANIFEST" --ood-report "$OOD_REPORT" \
  --output "$THRESHOLD_MANIFEST" --config "$CONFIG"

# ---- 14. final evaluation (12-vs-24 + fake-INT8 + channel OOD + recommendation) ----
step 14 "final evaluation (frozen thresholds; test + ood_final_test read once)"
scripts/run_final_evaluation.sh "$MANIFEST" "$THRESHOLD_MANIFEST"

# ---- 15. ONNX export (opset 17, operator whitelist + ORT parity) ----
step 15 "ONNX export (operator whitelist + ORT/argmax/OOD-score parity)"
scripts/run_export.sh "$MANIFEST"

# ---- 16. fake-INT8 verification (fp32 vs int8: accuracy drop + per-class recall + confusion) ----
step 16 "fake-INT8 verification (already recorded in formal + final evaluation)"
"$PYTHON" - <<'PY' 2>&1
import json
report = json.load(open("runs/final_evaluation/final_evaluation.json", encoding="utf-8"))
fi = report["candidates"]["rml24"]["fake_int8"]
print(f"fake_int8 fp32_acc={fi['fp32_accuracy']:.6f} int8_acc={fi['fake_int8_accuracy']:.6f} "
      f"drop={fi['accuracy_drop']:.6f}")
assert "fp32_per_class_recall" in fi and "fp32_confusion" in fi, "fake-INT8 report missing recall/confusion"
PY

# ---- 17. final artifact verification ----
step 17 "final artifact verification (existence + SHA)"
for f in "$MANIFEST" "$OOD_REPORT" "$THRESHOLD_MANIFEST" \
         "runs/final_evaluation/final_evaluation.json" \
         "runs/rml24_base/onnx/rml24_opset17.onnx" \
         "runs/rml24_base/onnx/export_manifest.json"; do
  [ -f "$f" ] || fail "missing final artifact $f"
done
sha256sum "$MANIFEST" "$THRESHOLD_MANIFEST" "runs/rml24_base/onnx/rml24_opset17.onnx"

RUN_ID="$RUN_ID" "$PYTHON" - <<'PY' 2>&1
import json, os
json.dump({"run_id": os.environ["RUN_ID"], "result": "PASS"},
          open("runs/autodl_rml24/run_manifest.json", "w", encoding="utf-8"),
          indent=2, sort_keys=True)
PY

echo ""
echo "============================================================"
echo "AUTODL_PIPELINE_RESULT result=PASS run_id=$RUN_ID"
echo "============================================================"
