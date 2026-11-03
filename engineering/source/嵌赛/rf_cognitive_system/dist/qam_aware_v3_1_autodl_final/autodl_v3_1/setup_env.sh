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

# Configurable package index.  AutoDL's default Aliyun mirror is deliberately
# NOT assumed.  Override with V3_PIP_INDEX_URL; default to Tsinghua, and fall
# back to the official PyPI index if the mirror is unreachable.
INDEX_URL="${V3_PIP_INDEX_URL:-https://pypi.tuna.tsinghua.edu.cn/simple}"
FALLBACK_URL="https://pypi.org/simple"

echo "Installing non-Torch dependencies from: ${INDEX_URL}"
# requirements_autodl_v3.txt intentionally excludes torch, so this can never
# replace or downgrade the CUDA-enabled PyTorch supplied by the image.
if ! python -m pip install --no-input -r requirements_autodl_v3.txt -i "${INDEX_URL}"; then
  echo "Mirror install failed; falling back to official PyPI (${FALLBACK_URL})."
  python -m pip install --no-input -r requirements_autodl_v3.txt -i "${FALLBACK_URL}"
fi

# Guard: confirm the image's CUDA-enabled torch survived unchanged.
python - <<'PY'
import torch
assert torch.cuda.is_available(), "CUDA became unavailable after dependency install"
print("torch_after_install=", torch.__version__, "cuda=", torch.version.cuda)
PY
