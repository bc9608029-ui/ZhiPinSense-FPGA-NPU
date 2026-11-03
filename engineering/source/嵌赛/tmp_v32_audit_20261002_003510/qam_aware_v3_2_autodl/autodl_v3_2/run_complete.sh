#!/usr/bin/env bash
set -euo pipefail

# One-command AutoDL workflow. It is safe to rerun after an interrupted job:
# formal training resumes from last.pt when that checkpoint exists.
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
# CUDA determinism for strict-resume and reproducible training results.
export CUBLAS_WORKSPACE_CONFIG=:4096:8

FORMAL_ROOT="outputs/qam_aware_v3_2/formal"
SMOKE_MARKER="outputs/qam_aware_v3_2/smoke/V3_2_AUTODL_SMOKE_PASS"
LAST_CHECKPOINT="${FORMAL_ROOT}/checkpoints/last.pt"
LOG_DIR="${FORMAL_ROOT}/logs"
mkdir -p "$LOG_DIR"

echo "[1/10] Checking CUDA and installing non-Torch dependencies"
bash autodl_v3_2/setup_env.sh

echo "[2/10] Running source tests and deployment/export smoke test"
if [[ -f "$SMOKE_MARKER" ]]; then
  echo "Smoke marker exists; keeping the previously passed smoke result."
else
  bash autodl_v3_2/run_smoke.sh
  mkdir -p "$(dirname "$SMOKE_MARKER")"
  touch "$SMOKE_MARKER"
fi

echo "[3/10] Auditing the formal synthetic dataset contract"
python -m evaluation.audit_qam_aware_v3_2_dataset --config configs/qam_aware_v3_2.yaml

echo "[4/10] Running the controlled ablations (A1-A3, train/validation only)"
bash autodl_v3_2/run_ablation.sh

echo "[5/10] Verifying the zero-gate initialization reproduces V2 exactly"
python - <<'PY'
import torch
from models.qam_aware_rfnet_v3_2 import build_qam_aware_v3_2, load_v2_into_v3_2
from models.qam_aware_rfnet import build_qam_aware_model
from training.qam_aware_v3_2_utils import load_qam_aware_v3_2_config
cfg = load_qam_aware_v3_2_config("configs/qam_aware_v3_2.yaml")
ckpt = torch.load(cfg["v2_checkpoint"], map_location="cpu", weights_only=False)
qa = ckpt["config"]["qam_aware"]
v2 = build_qam_aware_model(variant="time_power_phase", num_classes=8, **qa)
v2.load_state_dict(ckpt["model_state"], strict=True).eval()
m = build_qam_aware_v3_2(8, **cfg["model"])
load_v2_into_v3_2(m, ckpt)
m.eval()
torch.manual_seed(0)
diff = (m(torch.randn(8, 2, 1024)) - v2(torch.randn(8, 2, 1024))).abs().max().item()
assert float(m.core.gate.item()) == 0.0
assert diff < 1e-5, f"init logits differ from V2 by {diff}"
print("init_logits_match_v2=True max_abs_diff=", diff)
PY

echo "[6/10] Training V3.2 (automatic strict resume when last.pt exists)"
if [[ -f "$LAST_CHECKPOINT" ]]; then
  echo "Resuming formal training from $LAST_CHECKPOINT"
  python -m training.train_qam_aware_v3_2 \
    --config configs/qam_aware_v3_2.yaml \
    --resume "$LAST_CHECKPOINT" \
    2>&1 | tee -a "$LOG_DIR/autodl_console.log"
else
  echo "Starting a clean formal trajectory"
  python -m training.train_qam_aware_v3_2 \
    --config configs/qam_aware_v3_2.yaml \
    2>&1 | tee "$LOG_DIR/autodl_console.log"
fi

echo "[7/10] Running the exact V2-compatible evaluation"
python -m evaluation.evaluate_qam_aware_v3_2 --config configs/qam_aware_v3_2.yaml

echo "[8/10] Exporting deployment-compatible ONNX graphs"
python -m scripts.export_qam_aware_v3_2_onnx --config configs/qam_aware_v3_2.yaml

echo "[9/10] Applying promotion gates"
ACCEPTANCE_RC=0
python -m evaluation.check_qam_aware_v3_2_acceptance || ACCEPTANCE_RC=$?

echo "[10/10] Packaging all formal artifacts"
python -m scripts.package_qam_aware_v3_2_results

if [[ "$ACCEPTANCE_RC" -eq 0 ]]; then
  echo "V3_2_AUTODL_COMPLETE_PASS"
  echo "Download: outputs/qam_aware_v3_2/qam_aware_v3_2_formal_results.tar.gz"
  exit 0
fi

echo "V3_2_AUTODL_COMPLETE_TRAINED_BUT_GATE_FAILED"
echo "Training/evaluation/export completed, but V3.2 remains a challenger and V2 stays frozen as champion."
echo "Download the result archive for diagnosis: outputs/qam_aware_v3_2/qam_aware_v3_2_formal_results.tar.gz"
exit "$ACCEPTANCE_RC"
