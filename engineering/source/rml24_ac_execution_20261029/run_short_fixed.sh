#!/usr/bin/env bash
set -euo pipefail
R=/root/rml24_ac_execution_20261029
TEST="$R/candidate"
for i in $(seq 1 180); do
 if grep -q 'UI_BUILD_RESULT result=FAIL' "$R/build_ui_retry2.log"; then echo AC_BUILD_FAILED; exit 1; fi
 if grep -q 'UI_BUILD_RESULT result=PASS' "$R/build_ui_retry2.log" && test -x "$TEST/bin/board_ui_live_rml24_final"; then break; fi
 sleep 2
done
test -x "$TEST/bin/board_ui_live_rml24_final"
systemctl is-active rml24-ui rml24-receiver > "$R/original_units_before_short.txt" || true
systemctl cat rml24-ui rml24-receiver > "$R/original_units_before_short.txt.config"
stopped=0
restore(){ rc=$?; if [ "$stopped" = 1 ]; then systemctl start rml24-ui rml24-receiver; systemctl is-active rml24-ui rml24-receiver > "$R/units_after_short.txt" || true; fi; exit "$rc"; }
trap restore EXIT
systemctl stop rml24-receiver rml24-ui
stopped=1
if pgrep -x npu_stream >/dev/null; then echo NPU_OCCUPIED_REFUSE; exit 1; fi
bash "$R/launch_scripts/run_ac_candidate.sh" --test "$TEST" --legacy-root /root/amr_rescue_20261025 --model-dir /root/realrf_finetune_pilot1_test_1773373090/model_rml24_bf16 --run "$R/short_fixed01" --expect "$R/dependency_expect.txt" --python /root/miniconda3/envs/torch_v2.0.1_aarch64/bin/python3 --initial-mode FIXED --duration-sec 60
printf 'AC_SHORT_FIXED_COMPLETE\n'
