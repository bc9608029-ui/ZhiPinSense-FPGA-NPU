#!/usr/bin/env bash
# run_preflight.sh — offline CPU preflight / smoke test for the V2 pipeline.
set -euo pipefail

cd "$(dirname "$0")/.."
python3 scripts/preflight.py 2>&1
