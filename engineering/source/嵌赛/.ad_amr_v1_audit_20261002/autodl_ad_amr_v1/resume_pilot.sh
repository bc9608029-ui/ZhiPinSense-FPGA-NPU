#!/usr/bin/env bash
# AD-AMR V1 — resume the staged pilot from the last saved checkpoints.
#
# Re-runs scripts.run_pilot; run_training() in that driver resumes from the
# existing last.pt when a partial run is detected, so a killed pilot continues
# rather than restarting from scratch.
set -euo pipefail

export CUBLAS_WORKSPACE_CONFIG=:4096:8

echo "[resume_pilot] resuming staged pilot"
python -m scripts.run_pilot
