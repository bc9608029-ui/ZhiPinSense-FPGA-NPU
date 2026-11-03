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
./bin/test_delay_gate          || rc=1
./bin/test_result_frame_parse  || rc=1
./bin/test_ui_live             || rc=1
./test_board_build.sh          || rc=1
./test_cli_override.sh         || rc=1

if [ $rc -eq 0 ]; then
    echo "run_tests.sh: ALL HOST TESTS PASSED"
else
    echo "run_tests.sh: FAILURES" >&2
fi
exit $rc
