#!/usr/bin/env bash
set -euo pipefail

bash autodl_ad_amr_v1_1_data_v2/setup_env.sh
bash autodl_ad_amr_v1_1_data_v2/run_data_audit.sh
bash autodl_ad_amr_v1_1_data_v2/run_preflight.sh
bash autodl_ad_amr_v1_1_data_v2/run_public_pretrain.sh
bash autodl_ad_amr_v1_1_data_v2/run_pilot.sh
bash autodl_ad_amr_v1_1_data_v2/run_formal.sh
