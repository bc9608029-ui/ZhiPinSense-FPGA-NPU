#!/usr/bin/env bash
# run_baseline_reproduce.sh — Phase 1: reproduce V1 with the V2 baseline.
set -euo pipefail

cd "$(dirname "$0")/.."
python3 scripts/baseline_reproduce.py "$@" 2>&1
