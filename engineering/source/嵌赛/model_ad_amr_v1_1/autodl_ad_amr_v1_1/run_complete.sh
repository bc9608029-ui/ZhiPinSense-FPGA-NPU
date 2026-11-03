#!/usr/bin/env bash
set -euo pipefail
export CUBLAS_WORKSPACE_CONFIG=:4096:8

bash autodl_ad_amr_v1_1/setup_env.sh
bash autodl_ad_amr_v1_1/run_preflight.sh
bash autodl_ad_amr_v1_1/run_pilot.sh
bash autodl_ad_amr_v1_1/run_formal.sh
bash autodl_ad_amr_v1_1/package_results.sh
