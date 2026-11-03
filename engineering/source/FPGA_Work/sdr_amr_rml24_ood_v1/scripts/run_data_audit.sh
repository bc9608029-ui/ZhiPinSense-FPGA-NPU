#!/usr/bin/env bash
# M1 re-audit on the training machine (regenerates the machine-local mtime/index
# in audit.json while keeping the portable SHA-256 + split identical).
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"
CONFIG="${CONFIG:-configs/rml24_base.yaml}"

echo "[audit] RadioML2018.01A (SHA-256 + frozen split)"
if [ -n "${HDF5_PATH:-}" ]; then
  "$PYTHON" -m data_tools.audit_rml2018 --config "$CONFIG" --hdf5-path "$HDF5_PATH"
else
  "$PYTHON" -m data_tools.audit_rml2018 --config "$CONFIG"
fi
echo "RML24_DATA_AUDIT_OK"
