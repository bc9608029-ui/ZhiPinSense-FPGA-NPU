#!/usr/bin/env bash
# AD-AMR V1 — AutoDL environment setup.
#
# NEVER reinstalls torch or the CUDA runtime: the AutoDL image already ships a
# GPU-enabled torch.  This script only (1) verifies torch+CUDA, then (2) installs
# the small non-torch dependencies from requirements.txt.
set -euo pipefail

echo "[setup_env] verifying torch + CUDA (no reinstall)"
python - <<'PY'
import torch
assert torch.cuda.is_available(), "CUDA is not available on this host"
print("torch", torch.__version__, "| cuda", torch.version.cuda, "| device", torch.cuda.get_device_name(0))
PY

echo "[setup_env] installing non-torch dependencies"
pip install --quiet -r requirements.txt

echo "[setup_env] done"
