#!/usr/bin/env bash
set -euo pipefail

bash autodl_ad_amr_v1_1_data_v4_12class_robust/setup_env.sh
bash autodl_ad_amr_v1_1_data_v4_12class_robust/run_preflight.sh
bash autodl_ad_amr_v1_1_data_v4_12class_robust/run_pilot.sh

cat <<'EOF'
==============================================================
pilot 完成。formal 需要人工锁定步骤（防止自动把未审阅的候选送上正式）：
  1. 审阅 outputs/ad_amr_v1_1_data_v4_12class_robust/pilot/pilot_report.json
     与 selected_candidate.json，确认唯一候选达标；
  2. bash autodl_ad_amr_v1_1_data_v4_12class_robust/run_lock.sh
  3. bash autodl_ad_amr_v1_1_data_v4_12class_robust/run_formal.sh
==============================================================
EOF
