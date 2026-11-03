#!/usr/bin/env bash
# M20 data audit: model identity + OOD-U 3-split isolation + generator-shortcut.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONUNBUFFERED=1
exec python -m scripts.m20_data_audit "$@"
