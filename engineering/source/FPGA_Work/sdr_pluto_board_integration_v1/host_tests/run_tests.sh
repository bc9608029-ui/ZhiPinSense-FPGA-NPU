#!/usr/bin/env bash
# Build (if needed) and run every sdr_adapter host/board unit test.
# No iCraft, no SDR, no board required.  Exits nonzero on any failure.
set -euo pipefail
cd "$(dirname "$0")"

./build_host_tests.sh

./test_all
./test_nco
./test_attr_routing
./test_receiver_scale
./test_rx_format
./test_resampler
./test_sample_rate_negotiate
./test_pluto_tx
./test_device_state_guard
./test_frame_analysis

echo "run_tests.sh: all suites passed"
