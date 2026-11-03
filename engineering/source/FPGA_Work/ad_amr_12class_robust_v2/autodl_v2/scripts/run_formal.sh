#!/usr/bin/env bash
# run_formal.sh — full-budget multi-seed training of selected candidates.
set -euo pipefail

cd "$(dirname "$0")/.."
python3 -m v2.formal "$@" 2>&1
