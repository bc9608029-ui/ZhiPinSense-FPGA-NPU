#!/usr/bin/env bash
# run_data_audit.sh — verify the frozen signal/channel contract matches V1.
set -euo pipefail

cd "$(dirname "$0")/.."
python3 scripts/data_audit.py 2>&1
