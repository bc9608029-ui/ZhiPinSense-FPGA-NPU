#!/usr/bin/env bash
# M13/M14: Outlier Exposure + Energy training (RML2018_24_ROBUST_CANDIDATE).
# Only run when the OE trigger condition (baseline Energy far-AUROC is
# insufficient) is met; see README_AUTODL.md.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PYTHON:-python}"

echo "[oe] training RML2018_24_ROBUST_CANDIDATE with OE+Energy loss"
"$PYTHON" -m training.oe_run --config configs/oe_energy.yaml --trial seed3407

echo "RML24_OE_ENERGY_OK"
