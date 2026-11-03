#!/usr/bin/env bash
# Run the twelve-class chain host tests.  Exit code is non-zero on any failure.
set -euo pipefail
cd "$(dirname "$0")"

rc=0
./bin/test_chain_common        || rc=1
./bin/test_result_frame_v2     || rc=1
./bin/test_restore_semantics   || rc=1
./bin/test_contiguous_cli      || rc=1
./bin/test_npu_rearm           || rc=1
./bin/test_signal_presence     || rc=1
./bin/test_auto_level_control  || rc=1
./bin/test_dsp_measure         || rc=1
./bin/test_delay_gate          || rc=1
./bin/test_result_frame_parse  || rc=1
./bin/test_result_frame_v3      || rc=1
./bin/test_ui_live             || rc=1
./bin/test_ui_v3_pages         || rc=1
./bin/test_ui_layout_m19       || rc=1
./bin/test_mode_control        || rc=1
./bin/test_control_channel     || rc=1
./bin/test_touch_mode_control  || rc=1
./bin/test_display_integrity   || rc=1
./bin/test_display_diagnostic  || rc=1
./bin/test_ui_scheduler         || rc=1
./bin/test_work_mode_engine    || rc=1
./bin/test_rf_waveform_12class || rc=1
./bin/test_band_scan           || rc=1
./bin/test_producer_12class    || rc=1
./bin/test_touch               || rc=1
./bin/test_gate10_sequential   || rc=1
./bin/test_gate10_settle        || rc=1
./bin/test_no_signal_ambient   || rc=1
./bin/test_m22_runtime         || rc=1
./bin/test_rml23_merged        || rc=1
./bin/test_result_frame_rml23  || rc=1
./bin/test_ui_rml23            || rc=1
./bin/test_ui_boundary         || rc=1
./bin/test_rf_fix_rml23        || rc=1
./bin/test_golden_rml23        || rc=1
./bin/test_heartbeat_socket    || rc=1
./bin/test_live_rx_gating      || rc=1
./bin/test_ui_live_rx_process  || rc=1
./bin/test_control_socket_process || rc=1
./bin/test_capture_hook       || rc=1
./bin/test_tx_audit_rml23     || rc=1
./bin/test_synthetic_iq_generator || rc=1
./bin/test_synthetic_iq_runner    || rc=1
./bin/test_synthetic_iq_roundtrip || rc=1
./bin/test_iq_digital_loopback || rc=1
./bin/test_iq_digital_loopback_sequence || rc=1
./bin/test_route_e_raw_rx_output_fields || rc=1
./bin/test_iq_digital_loopback_sweep || rc=1
./bin/test_iq_digital_loopback_sync || rc=1
./bin/test_iq_rf_loopback || rc=1
./bin/test_iq_rf_loopback_level_sweep || rc=1
./bin/test_iq_rf_loopback_ab || rc=1
./bin/test_iq_rf_loopback_23class || rc=1
./bin/test_iq_rf_loopback_23class_fix9r || rc=1
./bin/test_iq_rf_loopback_23class_fix9r2 || rc=1
./bin/test_iq_rf_loopback_23class_fix9r2a || rc=1
./bin/test_iq_rf_fix9r2b || rc=1
./bin/test_iq_rf_fix9r2d || rc=1
./bin/test_iq_rf_loopback_23class_fix9r2g || rc=1
./bin/test_iq_rf_loopback_fix9r2g1_baseline_e2e || rc=1
./bin/test_iq_dual_sdr_fix10   || rc=1
./bin/test_iq_dual_sdr_23class_fix10   || rc=1
./bin/test_clean_iq_23class_fix10   || rc=1
./bin/test_pc_tx_protocol_fix10   || rc=1
./bin/test_pc_tx_board_rx_fix10   || rc=1
./bin/test_pc_tx_provenance_fix10   || rc=1
./bin/test_fix10_canonical_frame   || rc=1
./bin/test_rml24_raw_contract   || rc=1
./bin/test_rml24_bf16_baseline   || rc=1
./bin/test_clean_iq_24class_bf16_fix10   || rc=1
./bin/test_pc_tx_board_rx_24class_bf16_fix10   || rc=1
./bin/replay_fix10_failed_rx --self-test || rc=1
./bin/test_fix10class24_failed_rx_dump || rc=1
./bin/test_fix10class24_replay || rc=1
./bin/test_fix10class24_replay_canonical ../../board_capture/extracted/failed_rx/1500 || rc=1
./bin/replay_fix10class24_failed_rx --self-test || rc=1
./bin/replay_fix10class24_failed_rx --canonical-vs-runtime || rc=1
./bin/test_fix10class24_failed_rx_force_classify ../clean24_smoke ../../board_capture_extracted/rml24_rxbw_10000000_run1_1773377032/failed_rx/1500 || rc=1
./bin/test_dual_sdr_wide_linear || rc=1
./bin/test_fix10class24_noretrain_dump || rc=1
./bin/test_fix10class24_logits_fusion || rc=1
python3 ./test_fix10class24_failed_rx_force_classify.py || rc=1
python3 ./test_fix10class24_full24_failed_rx_forceclass1.py || rc=1
python3 ./test_pc_tx_protocol_fix10.py || rc=1
python3 ./test_pc_tx_iio_attr_parse.py || rc=1
python3 ./test_pc_tx_burst_cache.py || rc=1
python3 ./test_rml24_prewarm_plan.py || rc=1
python3 ./test_rml24_bf16_network_audit.py || rc=1
python3 ./test_fix10class24_rx_frontend_sweep.py || rc=1
./test_board_build.sh          || rc=1
./test_cli_override.sh         || rc=1
./test_rml23_build.sh          || rc=1

if [ $rc -eq 0 ]; then
    echo "run_tests.sh: ALL HOST TESTS PASSED"
else
    echo "run_tests.sh: FAILURES" >&2
fi
exit $rc
