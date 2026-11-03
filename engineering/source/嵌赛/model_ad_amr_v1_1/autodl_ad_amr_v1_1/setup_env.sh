#!/usr/bin/env bash
set -euo pipefail

echo "[setup] verifying the existing CUDA PyTorch runtime (torch is not reinstalled)"
python - <<'PY'
import torch
assert torch.cuda.is_available(), "CUDA is not available"
print("torch=", torch.__version__, "cuda=", torch.version.cuda,
      "device=", torch.cuda.get_device_name(0))
PY
pip install --quiet -r requirements.txt
echo "AD_AMR_V1_1_ENV_PASS"
