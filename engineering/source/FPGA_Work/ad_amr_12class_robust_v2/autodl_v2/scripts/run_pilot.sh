#!/usr/bin/env bash
# run_pilot.sh — V2 Phase A/B hyperparameter pilot (optuna or seeded fallback).
set -euo pipefail

cd "$(dirname "$0")/.."
python3 -m v2.pilot "$@" 2>&1
