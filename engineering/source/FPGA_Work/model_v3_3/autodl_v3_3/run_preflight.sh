#!/usr/bin/env bash
set -euo pipefail

# Preflight: a CUDA HARD GATE + a 2-epoch train/eval/ONNX-export FUNCTIONAL smoke.
#
# This script certifies only FUNCTIONAL correctness (code runs, checkpoints load,
# the real-model CUDA device paths hold, the ONNX operator gate holds).  It does
# NOT — and must not — certify performance readiness: a 2-epoch model is expected
# to be far from the 0.03 FPGA-sim floor.  Performance readiness is decided by the
# pilot (run_pilot.sh), whose predefined conditions are the only thing that lets
# run_complete.sh enter the formal 3-seed.
#
# CUDA is a hard requirement here: the script asserts ``torch.cuda.is_available()``
# and runs the real-model CUDA integration test (tests/test_qam_aware_v3_3_cuda.py).
# A CPU host therefore aborts before the marker is written — a skipped CUDA test is
# never accepted as a CUDA pass.
#
# The result is hash-guarded so a rerun keeps the previously passed result unless a
# key input (smoke/formal config, model, trainer + resume core, evaluator,
# acceptance, dataset/channel config, the V2 checkpoint, or any test/verification
# source) changed.
# Output is line-flushed so a partial run is observable in the AutoDL console.

cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD${PYTHONPATH:+:$PYTHONPATH}"
export CUBLAS_WORKSPACE_CONFIG=:4096:8

ROOT="outputs/qam_aware_v3_3"
MARKER="$ROOT/preflight/V3_3_PREFLIGHT_DONE"
mkdir -p "$(dirname "$MARKER")"

echo "[preflight/0] Asserting CUDA and printing the runtime"
python - <<'PY'
import torch
assert torch.cuda.is_available(), "CUDA is unavailable; the formal preflight must run on a GPU (a CPU skip is never a CUDA pass)."
print("torch=", torch.__version__)
print("cuda_version=", torch.version.cuda)
print("cudnn_version=", torch.backends.cudnn.version())
for i in range(torch.cuda.device_count()):
    print(f"device[{i}]=", torch.cuda.get_device_name(i), "capability=", torch.cuda.get_device_capability(i))
PY

V2_CHECKPOINT="init/v2_time_power_phase_best.pt"
V2_HASH=$(sha256sum "$V2_CHECKPOINT" | cut -d' ' -f1)

INPUT_HASH=$(
  cat \
    configs/qam_aware_v3_3_smoke.yaml \
    configs/qam_aware_v3_3.yaml \
    configs/qam_aware_v3_3_acceptance.yaml \
    configs/baseline.yaml \
    models/qam_aware_rfnet_v3_3.py \
    training/qam_aware_v3_3_trainer.py \
    training/resumable_trainer.py \
    training/trainer.py \
    training/utils.py \
    training/train_qam_aware_v3_3.py \
    evaluation/evaluate_qam_aware_v3_3.py \
    evaluation/evaluate_qam_aware_v3_3_ood.py \
    scripts/export_qam_aware_v3_3_onnx.py \
    scripts/verify_qam_aware_v3_3_init.py \
    tests/test_qam_aware_rfnet_v3_3.py \
    tests/test_qam_aware_v3_3_numeric_cpu.py \
    tests/test_qam_aware_v3_3_full_snr_cuda.py \
    tests/test_qam_aware_v3_3*.py \
  | sha256sum | cut -d' ' -f1
)
FULL_HASH=$(printf '%s %s\n' "$INPUT_HASH" "$V2_HASH" | sha256sum | cut -d' ' -f1)

if [[ -f "$MARKER" ]] && grep -q "$FULL_HASH" "$MARKER"; then
  echo "Preflight (CUDA gate + functional smoke) already passed for hash ($FULL_HASH); skipping."
  echo "V3_3_PREFLIGHT_FUNCTIONAL_PASS"
  exit 0
fi

echo "[preflight/1] Real-model CUDA integration test (release-blocking device paths)"
python -m pytest tests/test_qam_aware_v3_3_cuda.py -v

echo "[preflight/2] Full-SNR CUDA numerical-stability gate (A1/A2/A3, FP16 autocast, clamp, ONNX)"
python -m pytest tests/test_qam_aware_v3_3_full_snr_cuda.py -v

echo "[preflight/3] Running V3.3 source tests"
python -m pytest \
  tests/test_qam_aware_rfnet_v3_3.py \
  tests/test_qam_aware_v3_3_trainer.py \
  tests/test_qam_aware_v3_3_onnx_gate.py \
  tests/test_qam_aware_v3_3_selection.py \
  tests/test_qam_aware_v3_3_acceptance.py \
  tests/test_qam_aware_v3_3_packaging.py \
  tests/test_qam_aware_v3_3_dataset.py \
  tests/test_qam_aware_v3_3_data_isolation.py \
  tests/test_qam_aware_v3_3_numeric_cpu.py \
  -q

echo "[preflight/4] Running the 2-epoch smoke train"
python -m training.train_qam_aware_v3_3 --config configs/qam_aware_v3_3_smoke.yaml

echo "[preflight/5] Evaluating the smoke checkpoint"
python -m evaluation.evaluate_qam_aware_v3_3 --config configs/qam_aware_v3_3_smoke.yaml

echo "[preflight/6] Exporting smoke ONNX (hard 8-op gate)"
python -m scripts.export_qam_aware_v3_3_onnx --config configs/qam_aware_v3_3_smoke.yaml

printf 'passed hash=%s\n' "$FULL_HASH" > "$MARKER"
echo "V3_3_PREFLIGHT_FUNCTIONAL_PASS"
echo "Note: functional smoke only — performance readiness is decided by run_pilot.sh."
