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

echo "== build test_mode_control =="
$CXX $FLAGS test_mode_control.cpp -o bin/test_mode_control

echo "== build test_control_channel =="
$CXX $FLAGS test_control_channel.cpp -o bin/test_control_channel

echo "== build test_touch_mode_control =="
$CXX $FLAGS test_touch_mode_control.cpp -o bin/test_touch_mode_control

echo "== build test_display_integrity =="
$CXX $FLAGS test_display_integrity.cpp ../ui_sw/direct_framebuffer_backend.cpp -o bin/test_display_integrity

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

echo "build_host_tests.sh: OK -> host_tests/bin/{test_chain_common,test_result_frame_v2,test_restore_semantics,test_contiguous_cli,test_npu_rearm,test_signal_presence,test_auto_level_control,test_dsp_measure,test_delay_gate,test_result_frame_parse,test_result_frame_v3,test_ui_live,test_ui_v3_pages,test_mode_control,test_work_mode_engine,test_rf_waveform_12class,test_band_scan,test_producer_12class,test_touch,test_control_channel,test_touch_mode_control,test_display_integrity,test_ui_scheduler,test_gate10_sequential,test_gate10_settle,test_no_signal_ambient}"
