#!/usr/bin/env bash
# setup_env.sh — install non-torch Python dependencies on the AutoDL GPU image.
# torch (CUDA) is provided by the image and intentionally NOT reinstalled.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "installing python dependencies (torch excluded)..."
pip install -r requirements.txt 2>&1 | tail -n 20

echo "setup_env done"
