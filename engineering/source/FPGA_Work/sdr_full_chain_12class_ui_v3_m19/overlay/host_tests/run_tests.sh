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
./test_board_build.sh          || rc=1
./test_cli_override.sh         || rc=1

if [ $rc -eq 0 ]; then
    echo "run_tests.sh: ALL HOST TESTS PASSED"
else
    echo "run_tests.sh: FAILURES" >&2
fi
exit $rc
