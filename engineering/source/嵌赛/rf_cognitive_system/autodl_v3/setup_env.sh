#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."
python - <<'PY'
import torch
print("torch=", torch.__version__)
print("cuda_available=", torch.cuda.is_available())
if not torch.cuda.is_available():
    raise SystemExit("CUDA is unavailable. Select a GPU instance/image before formal training.")
print("gpu=", torch.cuda.get_device_name(0))
PY
python -m pip install -r requirements_autodl_v3.txt

