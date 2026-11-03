#!/usr/bin/env bash
# AD-AMR V1 — staged pilot (the sole performance gate before formal training).
#
# Requires the CUDA preflight to have passed first (its marker is NOT re-checked
# here by design; run preflight separately).  Prints AD_AMR_V1_PILOT_PASS or
# AD_AMR_V1_PILOT_NO_GO.  Touches only ad_amr_train / ad_amr_validation.
set -euo pipefail

export CUBLAS_WORKSPACE_CONFIG=:4096:8

echo "[pilot] starting staged pilot (Stage A: P0/P1 seed 2026 x8 epochs; Stage B: winner seeds 2026/2027 x15 epochs)"
python -m scripts.run_pilot
