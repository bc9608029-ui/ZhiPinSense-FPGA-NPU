#!/usr/bin/env bash
# Host (WSL/Linux) build of the twelve-class chain host tests.
# iCraft-free and libiio-free: exercises the exact chain_common.hpp / ui_report.hpp
# code the board runs, plus the stream resampler (resampler.cpp).
set -euo pipefail
cd "$(dirname "$0")"

CXX="${CXX:-g++}"
FLAGS="-std=gnu++17 -O2 -Wall -Wextra -Werror -I../board_package -I../sdr_adapter -I../ui_sw"

mkdir -p bin

echo "== build test_chain_common =="
$CXX $FLAGS test_chain_common.cpp ../sdr_adapter/resampler.cpp -o bin/test_chain_common

echo "== build test_result_frame_v2 =="
$CXX $FLAGS test_result_frame_v2.cpp -o bin/test_result_frame_v2

echo "== build test_restore_semantics =="
$CXX $FLAGS test_restore_semantics.cpp -o bin/test_restore_semantics

echo "== build test_contiguous_cli =="
$CXX $FLAGS test_contiguous_cli.cpp ../sdr_adapter/resampler.cpp -o bin/test_contiguous_cli

echo "== build test_npu_rearm =="
$CXX $FLAGS test_npu_rearm.cpp -o bin/test_npu_rearm

echo "== build test_signal_presence =="
$CXX $FLAGS test_signal_presence.cpp -o bin/test_signal_presence

echo "== build test_auto_level_control =="
$CXX $FLAGS test_auto_level_control.cpp -o bin/test_auto_level_control

echo "== build test_dsp_measure =="
$CXX $FLAGS test_dsp_measure.cpp -o bin/test_dsp_measure

echo "== build test_delay_gate =="
$CXX $FLAGS test_delay_gate.cpp -o bin/test_delay_gate

echo "== build test_result_frame_parse =="
$CXX $FLAGS test_result_frame_parse.cpp -o bin/test_result_frame_parse

echo "== build test_result_frame_v3 =="
$CXX $FLAGS test_result_frame_v3.cpp -o bin/test_result_frame_v3

echo "== build test_ui_live =="
$CXX $FLAGS test_ui_live.cpp ../ui_sw/font_atlas.cpp ../ui_sw/font_atlas_data.cpp ../ui_sw/ui_render.cpp -o bin/test_ui_live

echo "== build test_ui_v3_pages =="
$CXX $FLAGS test_ui_v3_pages.cpp ../ui_sw/font_atlas.cpp ../ui_sw/font_atlas_data.cpp ../ui_sw/ui_render.cpp -o bin/test_ui_v3_pages

echo "== build test_ui_layout_m19 =="
$CXX $FLAGS test_ui_layout_m19.cpp ../ui_sw/font_atlas.cpp ../ui_sw/font_atlas_data.cpp ../ui_sw/ui_render.cpp -o bin/test_ui_layout_m19

echo "== build make_ui_m19_snapshots =="
$CXX $FLAGS make_ui_m19_snapshots.cpp ../ui_sw/font_atlas.cpp ../ui_sw/font_atlas_data.cpp ../ui_sw/ui_render.cpp -o bin/make_ui_m19_snapshots

echo "== build test_mode_control =="
$CXX $FLAGS test_mode_control.cpp -o bin/test_mode_control

echo "== build test_control_channel =="
$CXX $FLAGS test_control_channel.cpp -o bin/test_control_channel

echo "== build test_touch_mode_control =="
$CXX $FLAGS test_touch_mode_control.cpp -o bin/test_touch_mode_control

echo "== build test_display_integrity =="
$CXX $FLAGS test_display_integrity.cpp ../ui_sw/direct_framebuffer_backend.cpp -o bin/test_display_integrity

echo "== build test_display_diagnostic =="
$CXX $FLAGS test_display_diagnostic.cpp ../ui_sw/direct_framebuffer_backend.cpp ../ui_sw/display_diagnostic.cpp -o bin/test_display_diagnostic

echo "== build test_ui_scheduler =="
$CXX $FLAGS test_ui_scheduler.cpp -o bin/test_ui_scheduler

echo "== build test_work_mode_engine =="
$CXX $FLAGS test_work_mode_engine.cpp -o bin/test_work_mode_engine

echo "== build test_rf_waveform_12class =="
$CXX $FLAGS test_rf_waveform_12class.cpp ../sdr_adapter/resampler.cpp -o bin/test_rf_waveform_12class

echo "== build test_band_scan =="
$CXX $FLAGS test_band_scan.cpp -o bin/test_band_scan

echo "== build test_producer_12class =="
$CXX $FLAGS test_producer_12class.cpp -o bin/test_producer_12class

echo "== build test_touch =="
$CXX $FLAGS test_touch.cpp -o bin/test_touch

echo "== build test_gate10_sequential =="
$CXX $FLAGS test_gate10_sequential.cpp ../sdr_adapter/resampler.cpp -o bin/test_gate10_sequential

echo "== build test_gate10_settle =="
$CXX $FLAGS test_gate10_settle.cpp -o bin/test_gate10_settle

echo "== build test_no_signal_ambient =="
$CXX $FLAGS test_no_signal_ambient.cpp -o bin/test_no_signal_ambient

echo "== build test_m22_runtime =="
$CXX $FLAGS test_m22_runtime.cpp -o bin/test_m22_runtime

echo "== build test_rml23_merged =="
$CXX $FLAGS test_rml23_merged.cpp -o bin/test_rml23_merged

echo "== build test_result_frame_rml23 =="
$CXX $FLAGS test_result_frame_rml23.cpp -o bin/test_result_frame_rml23

echo "== build test_ui_rml23 =="
$CXX $FLAGS test_ui_rml23.cpp ../ui_sw/font_atlas.cpp ../ui_sw/font_atlas_data.cpp ../ui_sw/ui_render.cpp -o bin/test_ui_rml23

echo "== build test_ui_boundary =="
$CXX $FLAGS test_ui_boundary.cpp ../ui_sw/font_atlas.cpp ../ui_sw/font_atlas_data.cpp ../ui_sw/ui_render.cpp -o bin/test_ui_boundary

echo "== build test_rf_fix_rml23 =="
$CXX $FLAGS test_rf_fix_rml23.cpp ../ui_sw/font_atlas.cpp ../ui_sw/font_atlas_data.cpp ../ui_sw/ui_render.cpp -o bin/test_rf_fix_rml23

echo "== build test_golden_rml23 =="
$CXX $FLAGS test_golden_rml23.cpp -o bin/test_golden_rml23

echo "== build test_heartbeat_socket =="
$CXX $FLAGS test_heartbeat_socket.cpp -o bin/test_heartbeat_socket

echo "== build test_live_rx_gating =="
$CXX $FLAGS test_live_rx_gating.cpp -o bin/test_live_rx_gating

echo "== build board_ui_live_rml23 (host, headless process-test target) =="
$CXX $FLAGS ../board_package/board_ui_live_rml23.cpp \
    ../ui_sw/direct_framebuffer_backend.cpp \
    ../ui_sw/font_atlas.cpp ../ui_sw/font_atlas_data.cpp ../ui_sw/ui_render.cpp \
    -o bin/board_ui_live_rml23

echo "== build test_ui_live_rx_process =="
$CXX $FLAGS -pthread test_ui_live_rx_process.cpp -o bin/test_ui_live_rx_process

echo "== build test_control_socket_process =="
$CXX $FLAGS -pthread test_control_socket_process.cpp -o bin/test_control_socket_process

echo "== build test_capture_hook =="
$CXX $FLAGS test_capture_hook.cpp -o bin/test_capture_hook

echo "== build test_tx_audit_rml23 =="
$CXX $FLAGS test_tx_audit_rml23.cpp ../sdr_adapter/resampler.cpp -o bin/test_tx_audit_rml23

echo "== build test_synthetic_iq_generator =="
$CXX $FLAGS test_synthetic_iq_generator.cpp ../sdr_adapter/resampler.cpp -o bin/test_synthetic_iq_generator

echo "== build test_synthetic_iq_runner =="
$CXX $FLAGS test_synthetic_iq_runner.cpp ../sdr_adapter/resampler.cpp -o bin/test_synthetic_iq_runner

echo "== build test_synthetic_iq_roundtrip =="
$CXX $FLAGS test_synthetic_iq_roundtrip.cpp ../sdr_adapter/resampler.cpp -o bin/test_synthetic_iq_roundtrip

echo "== build test_iq_digital_loopback =="
$CXX $FLAGS test_iq_digital_loopback.cpp -o bin/test_iq_digital_loopback

echo "== build test_iq_digital_loopback_sequence =="
$CXX $FLAGS test_iq_digital_loopback_sequence.cpp ../sdr_adapter/pluto_tx.cpp -o bin/test_iq_digital_loopback_sequence

echo "== build test_route_e_raw_rx_output_fields =="
$CXX $FLAGS test_route_e_raw_rx_output_fields.cpp ../sdr_adapter/resampler.cpp -o bin/test_route_e_raw_rx_output_fields

echo "== build test_iq_digital_loopback_sweep =="
$CXX $FLAGS test_iq_digital_loopback_sweep.cpp ../sdr_adapter/pluto_tx.cpp -o bin/test_iq_digital_loopback_sweep

echo "== build test_iq_digital_loopback_sync =="
$CXX $FLAGS test_iq_digital_loopback_sync.cpp ../sdr_adapter/pluto_tx.cpp -o bin/test_iq_digital_loopback_sync

echo "== build test_iq_rf_loopback =="
$CXX $FLAGS test_iq_rf_loopback.cpp ../sdr_adapter/pluto_tx.cpp -o bin/test_iq_rf_loopback

echo "== build test_iq_rf_loopback_level_sweep =="
$CXX $FLAGS test_iq_rf_loopback_level_sweep.cpp ../sdr_adapter/pluto_tx.cpp -o bin/test_iq_rf_loopback_level_sweep

echo "== build test_iq_rf_loopback_ab =="
$CXX $FLAGS test_iq_rf_loopback_ab.cpp -o bin/test_iq_rf_loopback_ab

echo "== build test_iq_rf_loopback_23class =="
$CXX $FLAGS test_iq_rf_loopback_23class.cpp ../sdr_adapter/pluto_tx.cpp -o bin/test_iq_rf_loopback_23class

echo "== build test_iq_rf_loopback_23class_fix9r =="
$CXX $FLAGS test_iq_rf_loopback_23class_fix9r.cpp ../sdr_adapter/pluto_tx.cpp -o bin/test_iq_rf_loopback_23class_fix9r

echo "== build test_iq_rf_loopback_23class_fix9r2 =="
$CXX $FLAGS test_iq_rf_loopback_23class_fix9r2.cpp ../sdr_adapter/pluto_tx.cpp -o bin/test_iq_rf_loopback_23class_fix9r2

echo "== build test_iq_rf_loopback_23class_fix9r2a =="
$CXX $FLAGS test_iq_rf_loopback_23class_fix9r2a.cpp -o bin/test_iq_rf_loopback_23class_fix9r2a

echo "== build test_iq_rf_fix9r2b =="
$CXX $FLAGS test_iq_rf_fix9r2b.cpp -o bin/test_iq_rf_fix9r2b

echo "== build test_iq_rf_fix9r2d =="
$CXX $FLAGS test_iq_rf_fix9r2d.cpp -o bin/test_iq_rf_fix9r2d

echo "== build test_iq_rf_loopback_23class_fix9r2g =="
$CXX $FLAGS test_iq_rf_loopback_23class_fix9r2g.cpp ../sdr_adapter/pluto_tx.cpp -o bin/test_iq_rf_loopback_23class_fix9r2g

echo "== build test_iq_rf_loopback_fix9r2g1_baseline_e2e =="
$CXX $FLAGS test_iq_rf_loopback_fix9r2g1_baseline_e2e.cpp -o bin/test_iq_rf_loopback_fix9r2g1_baseline_e2e

echo "== build test_iq_dual_sdr_fix10 =="
$CXX $FLAGS test_iq_dual_sdr_fix10.cpp -o bin/test_iq_dual_sdr_fix10

echo "== build test_iq_dual_sdr_23class_fix10 =="
$CXX $FLAGS test_iq_dual_sdr_23class_fix10.cpp -o bin/test_iq_dual_sdr_23class_fix10

echo "== build test_clean_iq_23class_fix10 =="
$CXX $FLAGS test_clean_iq_23class_fix10.cpp ../sdr_adapter/resampler.cpp -o bin/test_clean_iq_23class_fix10

echo "== build test_pc_tx_protocol_fix10 =="
$CXX $FLAGS test_pc_tx_protocol_fix10.cpp -o bin/test_pc_tx_protocol_fix10

echo "== build test_pc_tx_board_rx_fix10 =="
$CXX $FLAGS test_pc_tx_board_rx_fix10.cpp -o bin/test_pc_tx_board_rx_fix10

echo "== build test_pc_tx_provenance_fix10 =="
$CXX $FLAGS test_pc_tx_provenance_fix10.cpp -o bin/test_pc_tx_provenance_fix10

echo "== build test_fix10_canonical_frame =="
$CXX $FLAGS test_fix10_canonical_frame.cpp -o bin/test_fix10_canonical_frame

echo "== build test_rml24_raw_contract =="
$CXX $FLAGS test_rml24_raw_contract.cpp -o bin/test_rml24_raw_contract

echo "== build test_rml24_bf16_baseline =="
$CXX $FLAGS test_rml24_bf16_baseline.cpp -o bin/test_rml24_bf16_baseline

echo "== build test_clean_iq_24class_bf16_fix10 =="
$CXX $FLAGS test_clean_iq_24class_bf16_fix10.cpp ../sdr_adapter/resampler.cpp -o bin/test_clean_iq_24class_bf16_fix10

echo "== build test_pc_tx_board_rx_24class_bf16_fix10 =="
$CXX $FLAGS test_pc_tx_board_rx_24class_bf16_fix10.cpp -o bin/test_pc_tx_board_rx_24class_bf16_fix10

echo "== build replay_fix10_failed_rx =="
$CXX $FLAGS ../host_tools/replay_fix10_failed_rx.cpp -o bin/replay_fix10_failed_rx

echo "== build test_fix10class24_failed_rx_dump =="
$CXX $FLAGS test_fix10class24_failed_rx_dump.cpp -o bin/test_fix10class24_failed_rx_dump

echo "== build test_fix10class24_replay =="
$CXX $FLAGS test_fix10class24_replay.cpp -o bin/test_fix10class24_replay

echo "== build test_fix10class24_replay_canonical =="
$CXX $FLAGS test_fix10class24_replay_canonical.cpp -o bin/test_fix10class24_replay_canonical

echo "== build replay_fix10class24_failed_rx =="
$CXX $FLAGS ../host_tools/replay_fix10class24_failed_rx.cpp -o bin/replay_fix10class24_failed_rx

echo "== build test_fix10class24_failed_rx_force_classify =="
$CXX $FLAGS test_fix10class24_failed_rx_force_classify.cpp ../sdr_adapter/resampler.cpp -o bin/test_fix10class24_failed_rx_force_classify

echo "== build test_dual_sdr_wide_linear =="
$CXX $FLAGS test_dual_sdr_wide_linear.cpp -o bin/test_dual_sdr_wide_linear

echo "== build test_iq_rf_loopback_24class_bf16_fix10 =="
$CXX $FLAGS test_iq_rf_loopback_24class_bf16_fix10.cpp ../sdr_adapter/pluto_tx.cpp -o bin/test_iq_rf_loopback_24class_bf16_fix10

echo "build_host_tests.sh: OK -> host_tests/bin/{test_chain_common,test_result_frame_v2,test_restore_semantics,test_contiguous_cli,test_npu_rearm,test_signal_presence,test_auto_level_control,test_dsp_measure,test_delay_gate,test_result_frame_parse,test_result_frame_v3,test_ui_live,test_ui_v3_pages,test_ui_layout_m19,make_ui_m19_snapshots,test_mode_control,test_work_mode_engine,test_rf_waveform_12class,test_band_scan,test_producer_12class,test_touch,test_control_channel,test_touch_mode_control,test_display_integrity,test_display_diagnostic,test_ui_scheduler,test_gate10_sequential,test_gate10_settle,test_no_signal_ambient,test_m22_runtime,test_rml23_merged,test_result_frame_rml23,test_ui_rml23,test_rf_fix_rml23,test_golden_rml23,test_heartbeat_socket,test_live_rx_gating,board_ui_live_rml23,test_ui_live_rx_process,test_control_socket_process,test_capture_hook,test_tx_audit_rml23,test_synthetic_iq_generator,test_synthetic_iq_runner,test_synthetic_iq_roundtrip,test_iq_digital_loopback,test_iq_digital_loopback_sequence,test_route_e_raw_rx_output_fields,test_iq_digital_loopback_sweep,test_iq_digital_loopback_sync,test_iq_rf_loopback,test_iq_rf_loopback_level_sweep,test_iq_rf_loopback_ab,test_iq_rf_loopback_23class,test_iq_rf_loopback_23class_fix9r,test_iq_rf_loopback_23class_fix9r2,test_iq_rf_loopback_23class_fix9r2a,test_iq_rf_fix9r2b,test_iq_rf_fix9r2d,test_iq_rf_loopback_23class_fix9r2g,test_iq_rf_loopback_fix9r2g1_baseline_e2e,test_iq_dual_sdr_fix10,test_iq_dual_sdr_23class_fix10,test_clean_iq_23class_fix10,test_pc_tx_protocol_fix10,test_pc_tx_board_rx_fix10,test_pc_tx_provenance_fix10,test_fix10_canonical_frame,test_rml24_raw_contract,test_rml24_bf16_baseline,test_clean_iq_24class_bf16_fix10,test_pc_tx_board_rx_24class_bf16_fix10,test_fix10class24_failed_rx_dump,test_fix10class24_replay,test_fix10class24_replay_canonical,replay_fix10class24_failed_rx,test_fix10class24_failed_rx_force_classify,test_dual_sdr_wide_linear,test_iq_rf_loopback_24class_bf16_fix10}"
